from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field

from app.utils.time import now_ist


ThreatLevel = Literal["Low", "Medium", "High"]


class BoundingBox(BaseModel):
    label: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float


class EventBase(BaseModel):
    video_url: str = ""
    thumbnail_url: str = ""
    timestamp: datetime = Field(default_factory=now_ist)
    summary: str = ""
    threat_level: ThreatLevel = "Low"
    anomaly_score: float = 0.0
    detected_objects: list[BoundingBox] = Field(default_factory=list)
    escalation_steps: str = ""
    clip_path: str = ""
    source_id: str = "default"
    audio_transcription: str = ""
    owner_email: str = ""  # Email of the registered user who owns this camera/event


class EventCreate(EventBase):
    pass


class EventRead(EventBase):
    id: str = Field(alias="_id")


class PipelineStatus(BaseModel):
    running: bool
    source: str | None = None
    threat_level: ThreatLevel = "Low"
    fps: float = 0.0
    last_event_id: str | None = None
    message: str = "idle"


class ControlRequest(BaseModel):
    source: str | None = None
    owner_email: str = ""  # Email of the user starting this camera
    camera_mode: str = "normal"
    flash_url: str = ""


class UserRegister(BaseModel):
    """User registration request"""
    email: str  # User's email for receiving alerts
    name: str = "Security Admin"  # User's name
    camera_name: str = "Camera_1"  # Name/identifier of the camera


class UserRead(BaseModel):
    """User profile response"""
    id: str = Field(alias="_id")
    email: str
    name: str
    camera_name: str


class StreamMessage(BaseModel):
    """WebSocket message for live stream"""
    frame: str  # base64 encoded JPEG
    anomaly_score: float
    threat_level: ThreatLevel
    detected_objects: list[BoundingBox]
