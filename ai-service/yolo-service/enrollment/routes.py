import os
import tempfile
import base64
import cv2

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse

from enrollment.localization import localize_product
from enrollment.sessions import create_preview_session
from enrollment.selection import CropCandidate, select_best_crops
from enrollment.video import (
    extract_frames,
    VideoProcessingError,
)
from enrollment.approval import (
    load_approved_images,
    generate_embeddings,
    build_approval_response,
)
from enrollment.database import (
    save_product_embeddings,
    count_product_embeddings,
)
from events.kafka_producer import get_producer

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parent / "static"

MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class ApproveImagesRequest(BaseModel):
    session_id: str
    image_ids: list[str] = Field(min_length=1, max_length=10)


@router.get("/enroll", include_in_schema=False)
async def enroll_page():
    return FileResponse(STATIC_DIR / "enroll.html")


@router.get("/enroll.js", include_in_schema=False)
async def enroll_javascript():
    return FileResponse(
        STATIC_DIR / "enroll.js",
        media_type="application/javascript",
    )


@router.post("/api/products/preview", include_in_schema=False)
@router.post("/api/yolo/products/preview")
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


@router.post("/api/products/approve", include_in_schema=False)
@router.post("/api/yolo/products/approve")
async def approve_product_images(request: ApproveImagesRequest):
    session, images = load_approved_images(
        request.session_id,
        request.image_ids,
    )

    embeddings = await generate_embeddings(images)

    try:
        await run_in_threadpool(
            save_product_embeddings,
            session.sku,
            embeddings,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to save product embeddings to PostgreSQL",
        ) from exc

    # Publish a product-creation event (best effort; do not fail the request).
    try:
        producer = get_producer()
        producer.send_product_creation(
            name=session.sku,
            barcode=session.sku,
            initial_quantity=0,
            note=f"enrolled via yolo session {request.session_id}",
        )
        producer.flush(timeout=5.0)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "Failed to publish ProductCreationRequested event: %s", exc
        )

    return build_approval_response(
        session.sku,
        request.session_id,
        embeddings,
    )


@router.get("/api/products/db-status/{sku}", include_in_schema=False)
@router.get("/api/yolo/products/db-status/{sku}")
async def product_db_status(sku: str):
    """Return how many embeddings are stored for the given SKU."""
    try:
        count = await run_in_threadpool(count_product_embeddings, sku)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to read product status from PostgreSQL",
        ) from exc

    return {
        "sku": sku,
        "embedding_count": count,
        "exists": count > 0,
    }
