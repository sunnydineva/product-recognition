import os
import tempfile
from pathlib import Path

import cv2


PREVIEW_PATH = Path(tempfile.gettempdir()) / "product-recognition-camera-preview.jpg"


def save_preview(frame):
    """
    Encode an annotated camera frame as JPEG.

    Atomically replace the shared preview file so that the
    FastAPI streaming endpoint never reads a partially written image.
    """
    success, encoded = cv2.imencode(
        ".jpg",
        frame,
        [cv2.IMWRITE_JPEG_QUALITY, 75],
    )

    if not success:
        return

    temporary_path = PREVIEW_PATH.with_suffix(".tmp")

    with open(temporary_path, "wb") as file:
        file.write(encoded.tobytes())

    os.replace(temporary_path, PREVIEW_PATH)


def clear_preview():
    """
    Remove the previously published camera preview.

    Called when the camera starts or stops to prevent
    displaying stale frames from an earlier camera session.
    """
    PREVIEW_PATH.unlink(missing_ok=True)
