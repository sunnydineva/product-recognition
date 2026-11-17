import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from detection.best_crop import BestCropSaver
from detection.recognition import recognize_crop

logger = logging.getLogger(__name__)


class BrowserCameraSession:
    """Track browser camera objects and recognize finished tracks."""

    def __init__(self) -> None:
        self.model = YOLO("models/yolo11s.pt")
        self.crop_saver = BestCropSaver()
        self.recognition_worker = ThreadPoolExecutor(max_workers=1)

        self.pending_crops: dict[int, bytes] = {}
        self.submitted_tracks: set[int] = set()
        self.active_tracks: set[int] = set()
        self.missing_frames: dict[int, int] = {}

        self.max_missing_frames = 30

    def process_frame(self, image_bytes: bytes) -> dict:
        """Process one browser frame and update track state."""
        frame = cv2.imdecode(
            np.frombuffer(image_bytes, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )

        if frame is None:
            raise ValueError("Invalid JPEG frame")

        height, width = frame.shape[:2]

        results = self.model.track(
            frame,
            tracker="bytetrack.yaml",
            persist=True,
            verbose=False,
        )

        detections = []
        current_tracks: set[int] = set()

        for box in results[0].boxes:
            class_id = int(box.cls.item())
            class_name = self.model.names[class_id]

            if class_name in ("person", "tv"):
                continue

            track_id = int(box.id.item()) if box.id is not None else None

            bbox = box.xyxy[0].tolist()

            detections.append(
                {
                    "track_id": track_id,
                    "class_name": class_name,
                    "confidence": round(float(box.conf.item()), 3),
                    "bbox": bbox,
                }
            )

            if track_id is None:
                continue

            current_tracks.add(track_id)

            crop_path = self.crop_saver.save_if_better(
                frame,
                bbox,
                track_id,
            )

            if crop_path is not None:
                try:
                    self.pending_crops[track_id] = Path(crop_path).read_bytes()
                except OSError as error:
                    logger.error(
                        "Cannot read crop for track %s: %s",
                        track_id,
                        error,
                    )

        # Finish tracks that have disappeared.
        for track_id in self.active_tracks - current_tracks:
            self.missing_frames[track_id] = self.missing_frames.get(track_id, 0) + 1

            if self.missing_frames[track_id] >= self.max_missing_frames:
                self._submit_recognition(track_id)
                self.missing_frames.pop(track_id, None)

        # Visible tracks are no longer missing.
        for track_id in current_tracks:
            self.missing_frames.pop(track_id, None)

        self.active_tracks = current_tracks | set(self.missing_frames)

        print(
            f"[BROWSER CAMERA] Frame: {width}x{height}, "
            f"Detections: {len(detections)}, "
            f"Active tracks: {len(self.active_tracks)}",
            flush=True,
        )

        return {
            "width": width,
            "height": height,
            "detections": detections,
        }

    def _submit_recognition(self, track_id: int) -> None:
        """Submit the best crop for asynchronous recognition."""
        image_bytes = self.pending_crops.pop(track_id, None)

        if image_bytes is None or track_id in self.submitted_tracks:
            return

        self.submitted_tracks.add(track_id)

        print(
            f"[RECOGNITION] Submitting track {track_id} to DINOv2",
            flush=True,
        )

        self.recognition_worker.submit(
            recognize_crop,
            image_bytes,
            track_id,
        )

    def close(self) -> None:
        """Submit remaining tracks and release the worker."""
        for track_id in list(self.pending_crops):
            self._submit_recognition(track_id)

        self.recognition_worker.shutdown(wait=True)
