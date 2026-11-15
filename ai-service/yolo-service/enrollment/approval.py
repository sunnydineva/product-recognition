import httpx

from fastapi import HTTPException

from enrollment.dinov2_client import encode_image
from enrollment.sessions import (
    get_preview_session,
    get_selected_images,
    SessionNotFound,
    SessionExpired,
    InvalidImageSelection,
    SessionError,
)


def load_approved_images(session_id: str, image_ids: list[str]):
    try:
        session = get_preview_session(session_id)
        images = get_selected_images(session_id, image_ids)

        return session, images

    except (SessionNotFound, SessionExpired) as exc:
        raise HTTPException(
            status_code=404,
            detail="Preview session not found or expired",
        ) from exc

    except InvalidImageSelection as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except SessionError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


async def generate_embeddings(images) -> list[tuple[str, list[float]]]:
    embeddings = []

    try:
        for image in images:
            embedding = await encode_image(image.path)
            embeddings.append((image.image_id, embedding))

    except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Failed to generate DINOv2 embeddings",
        ) from exc

    return embeddings


def build_approval_response(
    sku: str,
    session_id: str,
    embeddings: list[tuple[str, list[float]]],
) -> dict:
    return {
        "status": "saved",
        "sku": sku,
        "session_id": session_id,
        "approved_count": len(embeddings),
        "embeddings": [
            {
                "image_id": image_id,
                "embedding_dimension": len(embedding),
            }
            for image_id, embedding in embeddings
        ],
        "saved_to_database": True,
    }
