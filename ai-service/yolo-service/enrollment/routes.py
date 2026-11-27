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
MAX_NAME_LENGTH = 255
MAX_NOTE_LENGTH = 2000
MAX_INITIAL_QUANTITY = 2147483647  # Avro int


def _initial_quantity(value: str) -> int:
    value = value.strip()
    if not value:
        return 0
    if not value.isascii() or not value.isdecimal() or len(value) > 10:
        raise HTTPException(status_code=422, detail="Invalid initial_quantity")
    quantity = int(value)
    if quantity > MAX_INITIAL_QUANTITY:
        raise HTTPException(status_code=422, detail="Invalid initial_quantity")
    return quantity


def _optional_text(value: str | None, max_length: int, field: str) -> str | None:
    """Trim an optional form field; blank input means no value."""
    if value is None:
        return None

    value = value.strip()

    if not value:
        return None

    if len(value) > max_length:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {field}",
        )

    return value


class ApproveImagesRequest(BaseModel):
    session_id: str
    image_ids: list[str] = Field(min_length=1, max_length=10)
    name: str | None = Field(default=None, max_length=MAX_NAME_LENGTH)
    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)
    initial_quantity: int | None = Field(default=None, strict=True, ge=0, le=MAX_INITIAL_QUANTITY)


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
@router.post("/api/yolo/products/preview", tags=["Enrollment"], summary="Подготовка на изображения за enrollment",
             description="Приема multipart video (до 25 MiB), sku и незадължителни name/note "
                         "и initial_quantity (цяло число 0–2147483647, по подразбиране 0). "
                         "Извлича кадри, локализира продукта и предлага качествени изображения "
                         "за избор. Връща preview данни и сесия при налични кандидати. "
                         "Подготвя временни данни, но не одобрява и не записва embeddings в PostgreSQL.")
async def preview_product(
    video: UploadFile = File(...),
    sku: str = Form(...),
    name: str | None = Form(None),
    note: str | None = Form(None),
    initial_quantity: str = Form("0"),
):
    sku = sku.strip()

    if not sku or len(sku) > 128:
        raise HTTPException(
            status_code=422,
            detail="Invalid SKU",
        )

    name = _optional_text(name, MAX_NAME_LENGTH, "name")
    note = _optional_text(note, MAX_NOTE_LENGTH, "note")
    quantity = _initial_quantity(initial_quantity)

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
                name=name,
                note=note,
                initial_quantity=quantity,
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
@router.post("/api/yolo/products/approve", tags=["Enrollment"], summary="Одобряване и запис на избрани изображения",
             description="Приема session_id, image_ids и незадължителни name/note от preview. "
                         "Генерира embeddings чрез DINOv2 и ги записва в AI PostgreSQL за SKU "
                         "на сесията. След записа опитва да публикува ProductCreationRequested "
                         "с initialQuantity от сесията или подаденото initial_quantity (по подразбиране 0). "
                         "Количеството се използва само за нов SKU; name пада към SKU при празно име. "
                         "Грешка при Kafka публикуване не отменя успешния DB запис; "
                         "брой изображения не означава складова наличност.")
async def approve_product_images(request: ApproveImagesRequest):
    session, images = load_approved_images(
        request.session_id,
        request.image_ids,
    )

    # An omitted request value keeps the session hint; an explicit blank clears it.
    name = (
        _optional_text(request.name, MAX_NAME_LENGTH, "name")
        if request.name is not None
        else session.name
    )
    note = (
        _optional_text(request.note, MAX_NOTE_LENGTH, "note")
        if request.note is not None
        else session.note
    )

    embeddings = await generate_embeddings(images)

    try:
        await run_in_threadpool(
            save_product_embeddings,
            session.sku,
            embeddings,
            name=name,
            note=note,
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
            name=name or session.sku,
            barcode=session.sku,
            initial_quantity=(request.initial_quantity if request.initial_quantity is not None
                              else session.initial_quantity),
            note=note,
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
@router.get("/api/yolo/products/db-status/{sku}", tags=["Enrollment"],
            summary="Проверка за записани embeddings по SKU",
            description="Връща sku, embedding_count и exists от AI PostgreSQL. "
                        "exists е true при поне един embedding. Това не е проверка на "
                        "inventory наличността; DB грешка връща 500.")
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
