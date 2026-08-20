from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx

from app.core.config import get_settings
from app.utils.time import now_ist, utc_now_iso_to_ist


@dataclass
class NotificationService:
    last_sent: dict[str, datetime] = field(default_factory=dict)

    async def send_email_alert(self, event_data: dict) -> bool:
        settings = get_settings()
        if event_data.get("threat_level") != "High":
            return False

        # Get recipient email from event (owner_email), not from config
        recipient = event_data.get("owner_email")
        if not recipient:
            # Fallback to config if owner_email not set
            recipients = settings.alert_recipient_list
            if not recipients:
                return False
            recipient = recipients[0]

        now = now_ist()
        last_sent = self.last_sent.get(recipient)
        if last_sent and now - last_sent < timedelta(seconds=settings.alert_cooldown_seconds):
            return False

        def to_absolute_url(path: str) -> str:
            if not path:
                return ""
            if path.startswith("http://") or path.startswith("https://"):
                return path
            return f"{settings.public_base_url.rstrip('/')}/{path.lstrip('/')}"

        payload = {
            "email": recipient,
            "subject": "Threat Detected - " + event_data.get("threat_level", "High"),
            "summary": event_data.get("summary", "Suspicious activity detected"),
            "threat_level": event_data.get("threat_level", "High"),
            "video_url": to_absolute_url(event_data.get("video_url", "")),
            "thumbnail_url": to_absolute_url(event_data.get("thumbnail_url", "")),
            "thumbnail_base64": event_data.get("thumbnail_base64", ""),
            "timestamp": utc_now_iso_to_ist(event_data.get("timestamp")),
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(settings.mailer_service_url, json=payload)
                response.raise_for_status()
                self.last_sent[recipient] = now
                return True
        except Exception:
            return False
