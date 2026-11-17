import logging
import os

import requests

logger = logging.getLogger(__name__)

DINOV2_RECOGNIZE_URL = os.environ["DINOV2_RECOGNIZE_URL"]


def recognize_crop(image_bytes: bytes, track_id: int) -> dict | None:
    """Recognize a saved product crop using DINOv2."""
    try:
        response = requests.post(
            DINOV2_RECOGNIZE_URL,
            files={
                "file": (
                    f"track_{track_id}.jpg",
                    image_bytes,
                    "image/jpeg",
                )
            },
            timeout=(2, 15),
        )
        response.raise_for_status()

        result = response.json()
        print(
            f"[RECOGNITION] Track ID={track_id} | DINOv2 result={result}",
            flush=True,
        )

        logger.info("DINOv2 | track %s: %s", track_id, result)
        return result

    except (requests.RequestException, ValueError) as error:
        logger.error(
            "DINOv2 | track %s: recognition failed: %s",
            track_id,
            error,
        )
        return None
