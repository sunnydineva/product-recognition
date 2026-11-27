
import shutil
import tempfile
import threading
import time
import uuid

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


SESSION_TTL_SECONDS = 30 * 60
MAX_IMAGES_PER_SESSION = 10

# Temporary directory managed by this module.
SESSIONS_DIR = Path(tempfile.gettempdir()) / "product-enrollment-sessions"

_lock = threading.RLock()


@dataclass(frozen=True)
class SessionImage:
    image_id: str
    timestamp_ms: int
    path: Path


@dataclass
class PreviewSession:
    session_id: str
    sku: str
    created_at: float
    images: list[SessionImage]
    name: str | None = None
    note: str | None = None


class SessionError(Exception):
    pass


class SessionNotFound(SessionError):
    pass


class SessionExpired(SessionError):
    pass


class InvalidImageSelection(SessionError):
    pass


def _session_dir(session_id: str) -> Path:
    return SESSIONS_DIR / session_id


def _delete_session_dir(session_id: str) -> None:
    shutil.rmtree(
        _session_dir(session_id),
        ignore_errors=True,
    )


def _read_metadata(session_id: str) -> PreviewSession:
    """
    Metadata is stored in memory for now.
    This implementation is intended for one Uvicorn worker.
    """
    session = _sessions.get(session_id)

    if session is None:
        raise SessionNotFound("Preview session not found")

    if time.time() - session.created_at > SESSION_TTL_SECONDS:
        _sessions.pop(session_id, None)
        _delete_session_dir(session_id)
        raise SessionExpired("Preview session expired")

    return session


_sessions: dict[str, PreviewSession] = {}


def cleanup_expired_sessions() -> int:
    """
    Removes expired sessions known to this process.
    Returns the number of removed sessions.
    """
    removed = 0

    with _lock:
        now = time.time()

        for session_id, session in list(_sessions.items()):
            if now - session.created_at > SESSION_TTL_SECONDS:
                _sessions.pop(session_id, None)
                _delete_session_dir(session_id)
                removed += 1

    return removed


def create_preview_session(
    sku: str,
    crops: list[tuple[int, np.ndarray]],
    name: str | None = None,
    note: str | None = None,
) -> PreviewSession:
    """
    crops: [(timestamp_ms, original_bgr_crop), ...]

    Saves up to 10 original-resolution crops as PNG files.
    """

    if not sku.strip():
        raise ValueError("SKU cannot be empty")

    if not crops:
        raise ValueError("No crops to save")

    if len(crops) > MAX_IMAGES_PER_SESSION:
        raise ValueError("Too many crops")

    cleanup_expired_sessions()

    session_id = uuid.uuid4().hex
    directory = _session_dir(session_id)

    images = []

    with _lock:
        directory.mkdir(
            parents=True,
            exist_ok=False,
        )

        try:
            for timestamp_ms, crop in crops:
                if (
                    crop is None
                    or not isinstance(crop, np.ndarray)
                    or crop.size == 0
                ):
                    raise ValueError("Invalid crop image")

                image_id = uuid.uuid4().hex
                path = directory / f"{image_id}.png"

                success = cv2.imwrite(str(path), crop)

                if not success:
                    raise SessionError(
                        "Could not save crop image"
                    )

                images.append(
                    SessionImage(
                        image_id=image_id,
                        timestamp_ms=timestamp_ms,
                        path=path,
                    )
                )

            session = PreviewSession(
                session_id=session_id,
                sku=sku.strip(),
                created_at=time.time(),
                images=images,
                name=name.strip() if name and name.strip() else None,
                note=note.strip() if note and note.strip() else None,
            )

            _sessions[session_id] = session

            return session

        except Exception:
            _delete_session_dir(session_id)
            raise


def get_preview_session(session_id: str) -> PreviewSession:
    with _lock:
        return _read_metadata(session_id)


def get_selected_images(
    session_id: str,
    image_ids: list[str],
) -> list[SessionImage]:
    """
    Validates image IDs against the session.
    Returns selected images in the requested order.
    """

    with _lock:
        session = _read_metadata(session_id)

        if not image_ids:
            raise InvalidImageSelection(
                "Select at least one image"
            )

        if len(image_ids) > MAX_IMAGES_PER_SESSION:
            raise InvalidImageSelection(
                "Too many selected images"
            )

        if len(set(image_ids)) != len(image_ids):
            raise InvalidImageSelection(
                "Duplicate image IDs"
            )

        available = {
            image.image_id: image
            for image in session.images
        }

        selected = []

        for image_id in image_ids:
            image = available.get(image_id)

            if image is None:
                raise InvalidImageSelection(
                    "Image does not belong to session"
                )

            if not image.path.is_file():
                raise SessionError(
                    "Selected image file is missing"
                )

            selected.append(image)

        return selected


def delete_preview_session(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)
        _delete_session_dir(session_id)
