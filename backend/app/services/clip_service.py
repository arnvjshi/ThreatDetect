from __future__ import annotations

from collections import deque
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Iterable

import cv2
import numpy as np

from app.schemas.event import BoundingBox
from app.utils.vision import FramePacket


class ClipService:
    def __init__(self, output_dir: str, pre_event_seconds: int, post_event_seconds: int) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnail_dir = self.output_dir.parent / "thumbnails"
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)
        self.pre_event_seconds = pre_event_seconds
        self.post_event_seconds = post_event_seconds

    def make_buffer(self, fps: int) -> deque[FramePacket]:
        maxlen = max(1, fps * self.pre_event_seconds)
        return deque(maxlen=maxlen)

    def save_clip(
        self,
        buffered_frames: Iterable[FramePacket],
        post_event_frames: Iterable[FramePacket],
        event_id: str,
        fps: int,
        audio_path: str = ""
    ) -> str:
        frames = [*buffered_frames, *post_event_frames]
        if not frames:
            return ""

        height, width = frames[0].frame.shape[:2]
        clip_path = self.output_dir / f"{event_id}.mp4"
        writer_fps = self._estimate_fps(frames, fallback_fps=fps)
        temp_path = self.output_dir / f"{event_id}.tmp.mp4"
        writer = cv2.VideoWriter(str(temp_path), cv2.VideoWriter_fourcc(*"mp4v"), float(writer_fps), (width, height))
        for packet in frames:
            writer.write(packet.frame)
        writer.release()

        ffmpeg_path = shutil.which("ffmpeg")
        if not ffmpeg_path:
            temp_path.replace(clip_path)
            return str(clip_path)

        command = [
            ffmpeg_path,
            "-y",
            "-i",
            str(temp_path)
        ]
        
        if audio_path and Path(audio_path).exists() and Path(audio_path).stat().st_size > 44:
            command.extend(["-i", str(audio_path)])
            command.extend(["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"])
            command.extend(["-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart"])
        else:
            command.extend(["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart"])
            
        command.append(str(clip_path))
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if completed.returncode != 0 or not clip_path.exists():
            temp_path.replace(clip_path)
        else:
            temp_path.unlink(missing_ok=True)

        return str(clip_path)

    @staticmethod
    def _estimate_fps(frames: list[FramePacket], fallback_fps: int) -> float:
        if len(frames) < 2:
            return float(max(1, fallback_fps))

        deltas = [
            current.timestamp - previous.timestamp
            for previous, current in zip(frames, frames[1:])
            if current.timestamp > previous.timestamp
        ]

        if not deltas:
            return float(max(1, fallback_fps))

        # Median delta is stable against occasional stalls/spikes.
        median_delta = float(np.median(np.array(deltas)))
        if median_delta <= 0:
            return float(max(1, fallback_fps))

        estimated_fps = 1.0 / median_delta
        return float(np.clip(estimated_fps, 1.0, 30.0))

    def save_thumbnail(self, frames: Iterable[FramePacket], event_id: str) -> str:
        frame_list = list(frames)
        if not frame_list:
            return ""

        frame = frame_list[len(frame_list) // 2].frame
        height, width = frame.shape[:2]
        if width > 640:
            scale = 640 / float(width)
            resized_height = max(1, int(height * scale))
            frame = cv2.resize(frame, (640, resized_height))
        thumbnail_path = self.thumbnail_dir / f"{event_id}.jpg"
        cv2.imwrite(str(thumbnail_path), frame)
        return str(thumbnail_path)
