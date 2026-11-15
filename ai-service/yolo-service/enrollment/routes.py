import os
import tempfile
import base64
import cv2
import httpx

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse

from enrollment.localization import localize_product
from enrollment.selection import CropCandidate, select_best_crops
from enrollment.sessions import (
    create_preview_session,
    get_selected_images,
    SessionNotFound,
    SessionExpired,
    InvalidImageSelection,
)
from enrollment.dinov2_client import encode_image
from enrollment.sessions import get_preview_session, SessionError

from enrollment.video import (
    extract_frames,
    VideoProcessingError,
)

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parent / "static"

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class ApproveImagesRequest(BaseModel):
    session_id: str
    image_ids: list[str] = Field(min_length=1, max_length=10)


@router.get("/enroll")
async def enroll_page():
    return FileResponse(STATIC_DIR / "enroll.html")


@router.get("/enroll.js")
async def enroll_javascript():
    return FileResponse(
        STATIC_DIR / "enroll.js",
        media_type="application/javascript",
    )


@router.post("/api/products/preview")
async def preview_product(
    video: UploadFile = File(...),
    sku: str = Form(...),
):
    sku = sku.strip()

    if not sku or len(sku) > 128:
        raise HTTPException(
            status_code=422,
            detail="Invalid SKU",
        )

    video_path = None
    total_bytes = 0

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".webm",
            delete=False,
        ) as temp_file:
            video_path = temp_file.name

            while chunk := await video.read(1024 * 1024):
                total_bytes += len(chunk)

                if total_bytes > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Video is too large",
                    )

                temp_file.write(chunk)

        try:
            # Run blocking OpenCV work outside the event loop.
            from starlette.concurrency import run_in_threadpool

            frames = await run_in_threadpool(
                extract_frames,
                video_path,
            )
        except VideoProcessingError as exc:
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc

        candidates = []

        for frame in frames:
            result = localize_product(frame.image)

            if result is None:
                continue

            candidates.append(
                CropCandidate(
                    timestamp_ms=frame.timestamp_ms,
                    product=result,
                )
            )

        selected = select_best_crops(
            candidates,
            max_crops=10,
        )

        # Save original-resolution crops in a temporary session.
        session = None

        if selected:
            session = create_preview_session(
                sku=sku,
                crops=[(item.timestamp_ms, item.product.crop) for item in selected],
            )

        localized = []

        if session is not None:
            for item, session_image in zip(
                selected,
                session.images,
            ):
                result = item.product

                preview_crop = result.crop.copy()

                height, width = preview_crop.shape[:2]
                scale = min(1.0, 320 / max(height, width))

                if scale < 1.0:
                    preview_crop = cv2.resize(
                        preview_crop,
                        None,
                        fx=scale,
                        fy=scale,
                        interpolation=cv2.INTER_AREA,
                    )

                success, encoded = cv2.imencode(
                    ".jpg",
                    preview_crop,
                    [cv2.IMWRITE_JPEG_QUALITY, 75],
                )

                if not success:
                    continue

                image_base64 = base64.b64encode(encoded.tobytes()).decode("ascii")

                localized.append(
                    {
                        "image_id": session_image.image_id,
                        "timestamp_ms": item.timestamp_ms,
                        "bbox": list(result.bbox),
                        "score": round(result.score, 3),
                        "sharpness": round(item.sharpness, 2),
                        "brightness": round(item.brightness, 2),
                        "quality_score": round(item.quality_score, 3),
                        "crop_shape": list(result.crop.shape),
                        "image": ("data:image/jpeg;base64," + image_base64),
                    }
                )

        return {
            "sku": sku,
            "session_id": (session.session_id if session is not None else None),
            "extracted_frames": len(frames),
            "localized_frames": len(candidates),
            "selected_frames": len(localized),
            "detections": localized,
        }

    finally:
        await video.close()

        if video_path and os.path.exists(video_path):
            os.remove(video_path)


@router.post("/api/products/approve")
async def approve_product_images(request: ApproveImagesRequest):
    try:
        session = get_preview_session(request.session_id)

        images = get_selected_images(
            request.session_id,
            request.image_ids,
        )

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

    embeddings = []

    try:
        for image in images:
            embedding = await encode_image(image.path)

            embeddings.append(
                {
                    "image_id": image.image_id,
                    "embedding_dimension": len(embedding),
                }
            )

    except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Failed to generate DINOv2 embeddings",
        ) from exc

    # Embeddings were generated successfully but are not persisted yet.
    # TODO: Save SKU and embeddings to PostgreSQL + pgvector.
    return {
        "status": "encoded",
        "sku": session.sku,
        "session_id": request.session_id,
        "approved_count": len(embeddings),
        "embeddings": embeddings,
        "saved_to_database": False,
    }
