from __future__ import annotations

import base64
import asyncio
import socket
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import cv2
import numpy as np
import httpx
from fastapi import WebSocket

from app.core.config import get_settings
from app.schemas.event import BoundingBox, EventCreate, PipelineStatus
from app.services.cnn_anomaly import CNNAnomalyService
from app.services.clip_service import ClipService
from app.services.db_service import DBService
from app.services.llm_service import LLMService
from app.services.notification_service import NotificationService
from app.services.yolo_service import YOLOService
from app.utils.time import now_ist
from app.utils.vision import FramePacket, draw_detections, encode_frame_to_jpeg


@dataclass
class StreamHub:
    clients: set[WebSocket] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def register(self, websocket: WebSocket) -> None:
        async with self.lock:
            self.clients.add(websocket)

    async def unregister(self, websocket: WebSocket) -> None:
        async with self.lock:
            self.clients.discard(websocket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead_clients: list[WebSocket] = []
        async with self.lock:
            clients = list(self.clients)
        for client in clients:
            try:
                await client.send_json(payload)
            except Exception:
                dead_clients.append(client)
        if dead_clients:
            async with self.lock:
                for client in dead_clients:
                    self.clients.discard(client)


@dataclass
class ActiveEvent:
    event_id: str
    detected_objects: list[BoundingBox]
    anomaly_score: float
    threat_level: str
    started_at: float
    buffer_snapshot: list[FramePacket]
    collected_frames: list[FramePacket] = field(default_factory=list)


class CameraPipeline:
    def __init__(
        self,
        hub: StreamHub,
        db_service: DBService,
        yolo_service: YOLOService,
        anomaly_service: CNNAnomalyService,
        clip_service: ClipService,
        llm_service: LLMService,
        notification_service: NotificationService,
    ) -> None:
        self.settings = get_settings()
        self.hub = hub
        self.db_service = db_service
        self.yolo_service = yolo_service
        self.anomaly_service = anomaly_service
        self.clip_service = clip_service
        self.llm_service = llm_service
        self.notification_service = notification_service

        self.loop: asyncio.AbstractEventLoop | None = None
        self.capture: cv2.VideoCapture | None = None
        self.thread: threading.Thread | None = None
        self.running = False
        self.use_snapshot_mode = False
        self.snapshot_url: str = ""
        self.source: str | None = None
        self.camera_mode: str = "normal"
        self.flash_url: str = ""
        self.owner_email: str = ""  # Email of user who started this camera
        self.status = PipelineStatus(running=False, message="idle")
        self.fps = max(1, int(self.settings.stream_target_fps))
        self.buffer = self.clip_service.make_buffer(self.fps)
        self._active_event: ActiveEvent | None = None
        self._last_event_group_started_at: float | None = None
        self._last_flash_at = 0.0
        self._last_frame = time.time()

    async def start(
        self,
        source: str | None = None,
        owner_email: str = "",
        camera_mode: str = "normal",
        flash_url: str = "",
    ) -> PipelineStatus:
        if self.running:
            return self.status

        self.loop = asyncio.get_running_loop()
        self.source = source or self.settings.video_source
        self.camera_mode = camera_mode or "normal"
        self.flash_url = flash_url.strip()
        self.owner_email = owner_email
        self._last_flash_at = 0.0
        self._last_event_group_started_at = None
        self.use_snapshot_mode = False
        self.snapshot_url = ""
        self.capture = None
        self._configure_source_mode()

        capture_fps = int(self.capture.get(cv2.CAP_PROP_FPS) or 0) if self.capture is not None else 0
        target_fps = max(1, int(self.settings.stream_target_fps))
        self.fps = min(capture_fps, target_fps) if capture_fps > 0 else target_fps
        self.buffer = self.clip_service.make_buffer(self.fps)
        self.running = True
        self.status = PipelineStatus(running=True, source=self.source, message="streaming")
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        await asyncio.sleep(0)
        return self.status

    async def stop(self) -> PipelineStatus:
        self.running = False
        if self.thread and self.thread.is_alive():
            await asyncio.to_thread(self.thread.join, 2.0)
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        self.status = PipelineStatus(running=False, source=self.source, message="stopped")
        return self.status

    def get_status(self) -> PipelineStatus:
        return self.status

    def _resolve_source(self, source: str) -> int | str:
        try:
            return int(source)
        except ValueError:
            return source

    def _resolve_capture_source(self, source: str) -> str:
        parsed = urlparse(source)
        if not parsed.scheme or not parsed.hostname:
            return source

        try:
            resolved_ip = socket.gethostbyname(parsed.hostname)
        except OSError:
            return source

        if parsed.hostname == resolved_ip:
            return source

        netloc = resolved_ip
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"

        return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))

    def _configure_source_mode(self) -> None:
        fallback_snapshot = self._to_snapshot_url(self.source)
        if self.camera_mode.lower() == "esp32" and fallback_snapshot:
            self.use_snapshot_mode = True
            self.snapshot_url = fallback_snapshot
            self._ensure_snapshot_available()
            return

        open_source = self._resolve_capture_source(self.source or self.settings.video_source)
        capture = cv2.VideoCapture(self._resolve_source(open_source))
        if self._capture_is_open(capture):
            self.capture = capture
            return

        if fallback_snapshot:
            self.use_snapshot_mode = True
            self.snapshot_url = fallback_snapshot
            self._ensure_snapshot_available()
            return

        raise RuntimeError(f"Unable to open video source: {self.source}")

    def _capture_is_open(self, capture: cv2.VideoCapture) -> bool:
        return bool(capture.isOpened())

    def _ensure_snapshot_available(self) -> None:
        snapshot_ok, _ = self._read_snapshot_frame()
        if not snapshot_ok:
            self.use_snapshot_mode = False
            self.snapshot_url = ""
            raise RuntimeError(f"Unable to open video source: {self.source}")

    def _run(self) -> None:
        while self.running:
            if self.use_snapshot_mode:
                success, frame = self._read_snapshot_frame()
            else:
                if self.capture is None or not self.capture.isOpened():
                    break
                success, frame = self.capture.read()

            if not success:
                time.sleep(0.05)
                continue

            frame_timestamp = time.time()
            frame = cv2.resize(frame, (self.settings.frame_width, self.settings.frame_height))
            yolo_result = self.yolo_service.detect(frame)
            anomaly_result = self.anomaly_service.analyze(frame)
            threat_level = self._compute_threat(yolo_result.detections, anomaly_result.score, yolo_result.suspicious)
            annotated = draw_detections(frame, yolo_result.detections, anomaly_result.score, frame_timestamp)
            packet = FramePacket(
                frame=annotated,
                timestamp=frame_timestamp,
                detections=yolo_result.detections,
                anomaly_score=anomaly_result.score,
                heatmap=anomaly_result.heatmap,
            )
            self.buffer.append(packet)
            self._broadcast_frame(packet, threat_level)
            self._maybe_trigger_flash(anomaly_result.score)
            self._process_event(packet, threat_level, yolo_result.detections)
            self._throttle()

    def _to_snapshot_url(self, source: str | None) -> str:
        if not source:
            return ""
        parsed = urlparse(source)
        if not parsed.scheme or not parsed.netloc:
            return ""

        path = parsed.path or ""
        if path.endswith("/stream"):
            snapshot_path = path[: -len("/stream")] + "/snapshot"
        elif path.endswith("stream"):
            snapshot_path = path[: -len("stream")] + "snapshot"
        else:
            return ""

        return urlunparse((parsed.scheme, parsed.netloc, snapshot_path, "", "", ""))

    def _read_snapshot_frame(self) -> tuple[bool, np.ndarray | None]:
        if not self.snapshot_url:
            return False, None

        try:
            with urllib.request.urlopen(self.snapshot_url, timeout=self.settings.snapshot_request_timeout_seconds) as response:
                data = response.read()
            frame_array = np.frombuffer(data, dtype=np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
            if frame is None:
                return False, None
            return True, frame
        except OSError:
            return False, None

    def _compute_threat(self, detections: list[BoundingBox], anomaly_score: float, suspicious: bool) -> str:
        weapon_hit = any(detection.label.lower() in {"weapon", "gun", "knife", "rifle", "pistol"} for detection in detections)
        score = max(anomaly_score, 1.0 if suspicious or weapon_hit else 0.0)
        if weapon_hit or score >= self.settings.event_threshold:
            return "High"
        if score >= self.settings.anomaly_threshold:
            return "Medium"
        return "Low"

    def _broadcast_frame(self, packet: FramePacket, threat_level: str) -> None:
        if self.loop is None:
            return
        payload = {
            "type": "frame",
            "timestamp": packet.timestamp,
            "threat_level": threat_level,
            "anomaly_score": packet.anomaly_score,
            "detections": [detection.model_dump() for detection in packet.detections],
            "frame": encode_frame_to_jpeg(packet.frame, quality=self.settings.stream_jpeg_quality),
        }
        self.loop.call_soon_threadsafe(asyncio.create_task, self.hub.broadcast(payload))

    def _maybe_trigger_flash(self, anomaly_score: float) -> None:
        if self.loop is None:
            return
        if self.camera_mode.lower() != "esp32":
            return
        if not self.flash_url:
            return
        if anomaly_score <= 0.30:
            return

        now = time.time()
        if now - self._last_flash_at < 2.0:
            return

        self._last_flash_at = now
        asyncio.run_coroutine_threadsafe(self._trigger_flash(), self.loop)

    async def _trigger_flash(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(self.flash_url, json={"duration": 2})
        except Exception:
            return

    def _process_event(self, packet: FramePacket, threat_level: str, detections: list[BoundingBox]) -> None:
        if self.loop is None:
            return

        should_trigger = threat_level in {"Medium", "High"} and (
            packet.anomaly_score >= self.settings.event_threshold or any(
                detection.label.lower() in {"weapon", "gun", "knife", "rifle", "pistol"} for detection in detections
            )
        )

        if should_trigger and self._active_event is None:
            if self._is_within_group_window(time.time()):
                return

            self._active_event = ActiveEvent(
                event_id=str(uuid4()),
                detected_objects=detections,
                anomaly_score=packet.anomaly_score,
                threat_level=threat_level,
                started_at=time.time(),
                buffer_snapshot=list(self.buffer),
            )
            self._mark_group_window(self._active_event.started_at)

        if self._active_event is None:
            return

        self._active_event.collected_frames.append(packet)
        elapsed = time.time() - self._active_event.started_at
        if elapsed >= self.settings.post_event_seconds:
            completed_event = self._active_event
            self._active_event = None
            self.loop.call_soon_threadsafe(asyncio.create_task, self._finalize_event(completed_event))

    async def _finalize_event(self, active_event: ActiveEvent) -> None:
        clip_path = await asyncio.to_thread(
            self.clip_service.save_clip,
            active_event.buffer_snapshot,
            active_event.collected_frames,
            active_event.event_id,
            self.fps,
        )
        thumbnail_path = await asyncio.to_thread(
            self.clip_service.save_thumbnail,
            [*active_event.buffer_snapshot, *active_event.collected_frames],
            active_event.event_id,
        )
        clip_name = Path(clip_path).name if clip_path else ""
        thumbnail_name = Path(thumbnail_path).name if thumbnail_path else ""
        video_url = f"/clips/{clip_name}" if clip_name else ""
        thumbnail_url = f"/thumbnails/{thumbnail_name}" if thumbnail_name else ""
        timestamp_ist = now_ist().isoformat()
        context = {
            "threat_level": active_event.threat_level,
            "anomaly_score": round(active_event.anomaly_score, 3),
            "detected_objects": [detection.model_dump() for detection in active_event.detected_objects],
            "timestamp_ist": timestamp_ist,
            "thumbnail_url": thumbnail_url,
        }
        thumbnail_bytes = Path(thumbnail_path).read_bytes() if thumbnail_path else None
        summary = await self.llm_service.generate_summary(context, thumbnail_bytes)
        thumbnail_base64 = base64.b64encode(thumbnail_bytes).decode("ascii") if thumbnail_bytes else ""
        event_data = EventCreate(
            video_url=video_url,
            thumbnail_url=thumbnail_url,
            timestamp=now_ist(),
            summary=summary.summary,
            threat_level=active_event.threat_level,
            anomaly_score=active_event.anomaly_score,
            detected_objects=active_event.detected_objects,
            escalation_steps=summary.escalation_steps,
            clip_path=clip_path,
            source_id=self.source or "default",
            owner_email=self.owner_email,  # Include the user's email who started this camera
        )
        event_id = await self.db_service.insert_event(event_data)
        await self.notification_service.send_email_alert(
            {
                "threat_level": active_event.threat_level,
                "summary": summary.summary,
                "video_url": video_url,
                "thumbnail_url": thumbnail_url,
                "thumbnail_base64": thumbnail_base64,
                "timestamp": now_ist().isoformat(),
                "event_id": event_id,
                "owner_email": self.owner_email,  # Pass email to notification service
            }
        )
        self.status = PipelineStatus(
            running=True,
            source=self.source,
            threat_level=active_event.threat_level,
            fps=self.fps,
            last_event_id=event_id,
            message="event processed",
        )
        await self.hub.broadcast(
            {
                "type": "event",
                "event_id": event_id,
                "threat_level": active_event.threat_level,
                "summary": summary.summary,
                "video_url": video_url,
                "thumbnail_url": thumbnail_url,
            }
        )

    def _is_within_group_window(self, timestamp: float) -> bool:
        window_seconds = max(1, int(self.settings.anomaly_group_window_seconds))
        if self._last_event_group_started_at is None:
            return False
        return (timestamp - self._last_event_group_started_at) < window_seconds

    def _mark_group_window(self, timestamp: float) -> None:
        self._last_event_group_started_at = timestamp

    def _throttle(self) -> None:
        frame_delay = 1.0 / max(self.fps, 1)
        elapsed = time.time() - self._last_frame
        if elapsed < frame_delay:
            time.sleep(frame_delay - elapsed)
        self._last_frame = time.time()
