from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ThreatDetect API"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"
    public_base_url: str = "http://localhost:8000"

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "threatdetect"

    video_source: str = "0"
    yolo_model_path: str = "yolov8n.pt"
    yolo_confidence: float = 0.4
    anomaly_threshold: float = 0.45
    event_threshold: float = 0.7
    anomaly_group_window_seconds: int = 120
    pre_event_seconds: int = 30
    post_event_seconds: int = 30
    clip_output_dir: str = "./storage/clips"
    frame_width: int = 1280
    frame_height: int = 720
    stream_target_fps: int = 12
    stream_jpeg_quality: int = 75
    snapshot_request_timeout_seconds: float = 1.2

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_timeout_seconds: float = 60.0
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    free_router_api_key: str = ""
    free_router_model: str = "google/gemini-3.8-pro-free"

    mailer_service_url: str = "http://localhost:5001/send-alert"
    alert_recipients: str = "security@example.com"
    alert_cooldown_seconds: int = 300

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def alert_recipient_list(self) -> List[str]:
        return [recipient.strip() for recipient in self.alert_recipients.split(",") if recipient.strip()]


@lru_cache

def get_settings() -> Settings:
    return Settings()
