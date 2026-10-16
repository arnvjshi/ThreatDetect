from __future__ import annotations

from dataclasses import dataclass

import cv2

from app.schemas.event import BoundingBox
from app.core.config import get_settings


@dataclass(slots=True)
class YoloResult:
    detections: list[BoundingBox]
    suspicious: bool


class YOLOService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.model = None
        self.class_names: dict[int, str] = {}
        try:
            from ultralytics import YOLO

            self.model = YOLO(self.settings.yolo_model_path)
            self.class_names = getattr(self.model, "names", {}) or {}
        except Exception:
            self.model = None
            self.class_names = {}

    def detect(self, frame) -> YoloResult:
        if self.model is None:
            return YoloResult(detections=[], suspicious=False)

        results = self.model.predict(frame, conf=self.settings.yolo_confidence, verbose=False)
        detections: list[BoundingBox] = []
        suspicious = False
        for result in results:
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                continue
            for box in boxes:
                class_id = int(box.cls[0]) if box.cls is not None else -1
                label = self.class_names.get(class_id, f"class_{class_id}")
                confidence = float(box.conf[0]) if box.conf is not None else 0.0
                x1, y1, x2, y2 = map(float, box.xyxy[0].tolist())
                detection = BoundingBox(label=label, confidence=confidence, x1=x1, y1=y1, x2=x2, y2=y2)
                detections.append(detection)
                if label.lower() in {"knife", "scissors", "baseball bat", "gun", "weapon", "pistol", "rifle"}:
                    suspicious = True
        return YoloResult(detections=detections, suspicious=suspicious)
