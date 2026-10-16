from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from zoneinfo import ZoneInfo

import cv2
import numpy as np

from app.schemas.event import BoundingBox


IST = ZoneInfo("Asia/Kolkata")


@dataclass(slots=True)
class FramePacket:
    frame: np.ndarray
    timestamp: float
    detections: list[BoundingBox]
    anomaly_score: float
    heatmap: np.ndarray | None = None
    audio_context: dict | None = None


def encode_frame_to_jpeg(frame: np.ndarray, quality: int = 75) -> str:
    jpeg_quality = int(np.clip(quality, 30, 95))
    success, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
    if not success:
        raise ValueError("Unable to encode frame")
    return base64.b64encode(buffer.tobytes()).decode("ascii")


def draw_detections(frame: np.ndarray, detections: Iterable[BoundingBox], anomaly_score: float, frame_timestamp: float | None = None) -> np.ndarray:
    output = frame.copy()
    for detection in detections:
        color = (80, 220, 180) if detection.label.lower() != "weapon" else (40, 80, 220)
        start = (int(detection.x1), int(detection.y1))
        end = (int(detection.x2), int(detection.y2))
        cv2.rectangle(output, start, end, color, 2)
        text = f"{detection.label} {detection.confidence:.2f}"
        cv2.putText(output, text, (start[0], max(24, start[1] - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

    status_text = f"Anomaly {anomaly_score:.2f}"
    cv2.putText(output, status_text, (24, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (240, 240, 240), 2)

    timestamp_value = frame_timestamp if frame_timestamp is not None else datetime.now().timestamp()
    timestamp_text = datetime.fromtimestamp(timestamp_value, tz=IST).strftime("%d-%b-%Y %H:%M:%S IST")
    cv2.putText(output, timestamp_text, (24, output.shape[0] - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (225, 235, 245), 2)
    return output
