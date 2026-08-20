from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import os
import re
import tempfile

import httpx

from app.core.config import get_settings


@dataclass(slots=True)
class SummaryPayload:
    summary: str
    escalation_steps: str


class LLMService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.logger = logging.getLogger("app.llm")

    async def generate_summary(self, event_context: dict, thumbnail_bytes: bytes | None = None) -> SummaryPayload:
        self.logger.info("LLM summary generation started", extra={"threat_level": event_context.get("threat_level")})
        ollama_response = await self._try_ollama(event_context)
        if ollama_response:
            self.logger.info("LLM summary generated via Ollama")
            return ollama_response
        self.logger.warning("Ollama summary failed; attempting Gemini")
        gemini_response = await self._try_gemini(event_context, thumbnail_bytes)
        if gemini_response:
            self.logger.info("LLM summary generated via Gemini")
            return gemini_response
        self.logger.error("LLM summary generation failed: both providers unavailable")
        return SummaryPayload(
            summary="Suspicious activity detected with no LLM fallback available.",
            escalation_steps="Review the clip, validate the detection, and notify security.",
        )

    async def _try_ollama(self, event_context: dict) -> SummaryPayload | None:
        prompt = self._prompt(event_context)
        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/generate"
        try:
            timeout = httpx.Timeout(self.settings.ollama_timeout_seconds)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url,
                    json={"model": self.settings.ollama_model, "prompt": prompt, "stream": False},
                )
                response.raise_for_status()
                data = response.json()
                text = data.get("response", "").strip()
                if not text:
                    self.logger.warning("Ollama returned empty response", extra={"url": url})
                    return None
                return self._parse_response(text)
        except httpx.ReadTimeout as exc:
            self.logger.warning("Ollama summary timed out", extra={"url": url, "timeout": self.settings.ollama_timeout_seconds, "error": str(exc)})
            return None
        except Exception as exc:
            self.logger.exception("Ollama summary failed", extra={"url": url, "error": str(exc)})
            return None

    async def _try_gemini(self, event_context: dict, thumbnail_bytes: bytes | None = None) -> SummaryPayload | None:
        if not self.settings.gemini_api_key:
            self.logger.warning("Gemini API key missing; skipping Gemini")
            return None
        try:
            import google.generativeai as genai

            genai.configure(api_key=self.settings.gemini_api_key)
            model = genai.GenerativeModel(self.settings.gemini_model)
            prompt = self._prompt(event_context)
            response = None
            temp_path = None
            image_part = None
            if thumbnail_bytes:
                try:
                    from PIL import Image
                    import io

                    image_part = Image.open(io.BytesIO(thumbnail_bytes))
                    self.logger.info("Gemini using inline image (PIL)")
                except Exception as exc:
                    self.logger.warning("PIL image decode failed; will try upload_file", extra={"error": str(exc)})

            if thumbnail_bytes and image_part is None:
                try:
                    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                        tmp.write(thumbnail_bytes)
                        temp_path = tmp.name
                    image_part = genai.upload_file(temp_path, mime_type="image/jpeg")
                    self.logger.info("Gemini using uploaded image file", extra={"path": temp_path})
                except Exception as exc:
                    self.logger.warning("Gemini upload_file failed; falling back to text", extra={"error": str(exc)})

            if image_part is not None:
                response = await asyncio.to_thread(model.generate_content, [prompt, image_part])
            else:
                response = await asyncio.to_thread(model.generate_content, prompt)

            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
            text = getattr(response, "text", "") or ""
            if not text:
                self.logger.warning("Gemini returned empty response", extra={"model": self.settings.gemini_model})
                return None
            return self._parse_response(text)
        except Exception as exc:
            self.logger.exception("Gemini summary failed", extra={"model": self.settings.gemini_model, "error": str(exc)})
            return None

    def _prompt(self, event_context: dict) -> str:
        timestamp_ist = event_context.get("timestamp_ist", "")
        return (
            "Summarize this security event in markdown with three sections: "
            "**Scene Summary**, **Threat Explanation**, **Escalation Steps**. "
            "Use concise professional language and bullet points for escalation steps. "
            f"Timestamp (IST): {timestamp_ist}. "
            "Event context: "
            f"{event_context}"
        )

    def _parse_response(self, text: str) -> SummaryPayload:
        normalized = text.replace("\r", "\n").strip()
        flat = " ".join(normalized.split())
        flat_lower = flat.lower()
        markers = ["scene summary", "threat explanation", "escalation steps"]
        positions: list[tuple[int, str]] = []
        for marker in markers:
            match = re.search(rf"\b{re.escape(marker)}\b", flat_lower)
            if match:
                positions.append((match.start(), marker))

        if positions:
            positions.sort()
            sections: dict[str, str] = {}
            for index, (start, marker) in enumerate(positions):
                content_start = start + len(marker)
                content_end = positions[index + 1][0] if index + 1 < len(positions) else len(flat)
                content = flat[content_start:content_end].strip(" :.-")
                sections[marker] = content

            scene = sections.get("scene summary", "")
            threat = sections.get("threat explanation", "")
            escalation = sections.get("escalation steps", "")

            summary = f"**Scene Summary:** {scene}" if scene else flat
            escalation_blocks: list[str] = []
            if threat:
                escalation_blocks.append(f"**Threat Explanation:** {threat}")
            if escalation:
                escalation_blocks.append(f"**Escalation Steps:** {escalation}")
            escalation_steps = "\n\n".join(escalation_blocks) if escalation_blocks else "Escalate to on-duty security staff."
            return SummaryPayload(summary=summary, escalation_steps=escalation_steps)

        lines = [line.strip("- ") for line in normalized.splitlines() if line.strip()]
        summary = lines[0] if lines else normalized
        escalation_steps = " ".join(lines[1:]) if len(lines) > 1 else "Escalate to on-duty security staff."
        return SummaryPayload(summary=summary, escalation_steps=escalation_steps)
