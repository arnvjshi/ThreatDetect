from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

import httpx

from app.core.config import get_settings
from app.utils.time import now_ist, utc_now_iso_to_ist

logger = logging.getLogger("app.notification")


@dataclass
class NotificationService:
    last_sent: dict[str, datetime] = field(default_factory=dict)

    async def send_email_alert(self, event_data: dict) -> bool:
        settings = get_settings()
        threat_level = event_data.get("threat_level", "Low")
        if threat_level not in {"High", "Medium"}:
            return False

        # Determine best recipient email
        recipient = (event_data.get("owner_email") or "").strip()
        # Fallback if owner_email is empty or default test placeholder
        if not recipient or "@example.com" in recipient or "@threatdetect.local" in recipient:
            valid_config_recipients = [r for r in settings.alert_recipient_list if "@example.com" not in r]
            if valid_config_recipients:
                recipient = valid_config_recipients[0]
            elif settings.email_user:
                recipient = settings.email_user
            elif event_data.get("owner_email"):
                recipient = event_data["owner_email"]
            elif settings.alert_recipient_list:
                recipient = settings.alert_recipient_list[0]

        if not recipient:
            logger.warning("No recipient email specified; skipping email alert")
            return False

        now = now_ist()
        last_sent = self.last_sent.get(recipient)
        if last_sent and now - last_sent < timedelta(seconds=settings.alert_cooldown_seconds):
            logger.info("Alert cooldown active for %s; skipping email", recipient)
            return False

        def to_absolute_url(path: str) -> str:
            if not path:
                return ""
            if path.startswith("http://") or path.startswith("https://"):
                return path
            return f"{settings.public_base_url.rstrip('/')}/{path.lstrip('/')}"

        payload = {
            "email": recipient,
            "subject": f"Threat Detected [{threat_level}]",
            "summary": event_data.get("summary", "Suspicious activity detected"),
            "threat_level": threat_level,
            "video_url": to_absolute_url(event_data.get("video_url", "")),
            "thumbnail_url": to_absolute_url(event_data.get("thumbnail_url", "")),
            "thumbnail_base64": event_data.get("thumbnail_base64", ""),
            "timestamp": utc_now_iso_to_ist(event_data.get("timestamp")),
        }
        try:
            logger.info("Sending %s threat email alert to %s via %s", threat_level, recipient, settings.mailer_service_url)
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(settings.mailer_service_url, json=payload)
                response.raise_for_status()
                self.last_sent[recipient] = now
                logger.info("Email alert successfully delivered to %s", recipient)
                return True
        except Exception as exc:
            logger.error("Failed to send email alert to %s: %s", recipient, exc)
            return False
