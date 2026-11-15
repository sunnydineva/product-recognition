
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class VideoFrame:
    timestamp_ms: int
    image: np.ndarray


class VideoProcessingError(Exception):
    pass


def extract_frames(
    video_path: str | Path,
    sample_fps: float = 3.0,
    max_duration_seconds: float = 15.0,
    max_frames: int = 45,
    max_decoded_frames: int = 900,
    max_pixels: int = 1920 * 1080,
) -> list[VideoFrame]:
    """
    Extract evenly spaced frames from a short video.

    Does not perform object detection or write image files.
    """

    if sample_fps <= 0 or max_frames <= 0:
        raise ValueError("Invalid sampling configuration")

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        cap.release()
        raise VideoProcessingError("Cannot open video")

    frames: list[VideoFrame] = []

    try:
        fps = cap.get(cv2.CAP_PROP_FPS)

        if not np.isfinite(fps) or fps <= 0:
            raise VideoProcessingError("Invalid video FPS")

        reported_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)

        if np.isfinite(reported_count) and reported_count > 0:
            reported_duration = reported_count / fps
            if reported_duration > max_duration_seconds:
                raise VideoProcessingError("Video is too long")

        interval = 1.0 / sample_fps
        next_sample_time = 0.0
        decoded_count = 0

        while True:
            success, frame = cap.read()

            if not success:
                break

            decoded_count += 1

            if decoded_count > max_decoded_frames:
                raise VideoProcessingError(
                    "Video exceeds decoding limit"
                )

            timestamp_seconds = (decoded_count - 1) / fps

            if timestamp_seconds > max_duration_seconds:
                raise VideoProcessingError("Video is too long")

            height, width = frame.shape[:2]

            if width * height > max_pixels:
                raise VideoProcessingError(
                    "Video resolution is too large"
                )

            if timestamp_seconds + 1e-6 < next_sample_time:
                continue

            frames.append(
                VideoFrame(
                    timestamp_ms=round(timestamp_seconds * 1000),
                    image=frame.copy(),
                )
            )

            next_sample_time += interval

            if len(frames) >= max_frames:
                break

        if not frames:
            raise VideoProcessingError(
                "Video contains no readable frames"
            )

        return frames

    finally:
        cap.release()
