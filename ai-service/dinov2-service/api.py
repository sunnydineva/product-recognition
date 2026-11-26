from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from pydantic import BaseModel, ConfigDict, Field

from dinov2_encoder import get_encoder, InvalidImageError
from recognition.database import find_similar_products
from events.kafka_producer import get_producer
from recognition.settings import (
    SettingsUnavailableError,
    get_min_similarity,
    is_finite_number,
    set_min_similarity,
)


CATALOG_DIR = Path(__file__).resolve().parent / "catalog"


app = FastAPI(
    title="Product Recognition API — DINOv2",
    description=(
        "API for recognizing previously enrolled products using "
        "DINOv2 visual embeddings and similarity matching."
    ),
    version="1.0.0",
    docs_url="/recognize/docs",
    openapi_url="/recognize/openapi.json",
    redoc_url="/recognize/redoc",
    swagger_ui_oauth2_redirect_url="/recognize/docs/oauth2-redirect",
)


@app.get("/openapi.json", include_in_schema=False)
def legacy_openapi():
    return app.openapi()


@app.get("/docs", include_in_schema=False)
def legacy_docs():
    return get_swagger_ui_html(openapi_url=app.openapi_url, title=app.title)


@app.get("/redoc", include_in_schema=False)
def legacy_redoc():
    return get_redoc_html(openapi_url=app.openapi_url, title=app.title)


@app.get("/docs/oauth2-redirect", include_in_schema=False)
def legacy_oauth_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/health", include_in_schema=False)
@app.get("/recognize/health", include_in_schema=False)
@app.get("/api/recognition/health")
def health():
    return {"status": "ok"}


class RecognitionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minSimilarity: float = Field(
        strict=True, ge=0, le=1, allow_inf_nan=False,
        description="Global cosine similarity ratio (0–1), not a probability. "
                    "Persisted default is 0.30; equality is accepted.",
    )


@app.exception_handler(RequestValidationError)
async def settings_validation_error(request, error):
    if request.url.path == "/api/recognition/settings":
        # Do not echo raw input: JSON cannot serialize rejected NaN/Infinity.
        return JSONResponse(status_code=422, content={
            "detail": [
                {key: item[key] for key in ("type", "loc", "msg")}
                for item in error.errors()
            ]
        })
    return await request_validation_exception_handler(request, error)


@app.get("/api/recognition/settings", response_model=RecognitionSettings)
def get_recognition_settings():
    try:
        return {"minSimilarity": get_min_similarity()}
    except SettingsUnavailableError as error:
        raise HTTPException(status_code=503, detail="Recognition settings unavailable") from error


@app.patch("/api/recognition/settings", response_model=RecognitionSettings)
def patch_recognition_settings(settings: RecognitionSettings):
    """Require minSimilarity; empty/null patches are rejected without mutation."""
    try:
        return {"minSimilarity": set_min_similarity(settings.minSimilarity)}
    except SettingsUnavailableError as error:
        raise HTTPException(status_code=503, detail="Recognition settings unavailable") from error


# Generate an embedding from the uploaded image
@app.post("/encode", include_in_schema=False)
@app.post("/api/recognition/encode")
def encode_image(file: UploadFile = File(...)):
    try:
        image_bytes = file.file.read()

        encoder = get_encoder()
        embedding = encoder.encode(image_bytes)

        return {"embedding_dimension": len(embedding), "embedding": embedding.tolist()}

    except InvalidImageError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except Exception:
        raise HTTPException(status_code=500, detail="Failed to encode image")


# Recognize a product using its image
@app.post("/recognize", include_in_schema=False)
@app.post("/api/recognition/recognize")
def recognize(file: UploadFile = File(...)):
    # Fail closed before encoding, matching or publishing if configuration is unavailable.
    try:
        min_similarity = get_min_similarity()
    except SettingsUnavailableError as error:
        raise HTTPException(status_code=503, detail="Recognition settings unavailable") from error

    try:
        image_bytes = file.file.read()

        encoder = get_encoder()
        embedding = encoder.encode(image_bytes)

        matches = find_similar_products(
            embedding.tolist(),
            limit=1,
        )
        matches = [
            match for match in matches
            if is_finite_number(match.get("similarity"))
            and match["similarity"] >= min_similarity
        ]

        if matches:
            try:
                match = matches[0]
                producer = get_producer()
                producer.send_stock_adjustment(
                    product_id=match["product_id"],
                    quantity=1,
                    operation="DECREASE",
                    note="recognized via dinov2",
                )
                producer.flush(timeout=5.0)
            except Exception as exc:
                import logging

                logging.getLogger(__name__).warning(
                    "Failed to publish StockAdjustmentRequested event: %s", exc
                )

        return {
            "status": "matched" if matches else "unknown",
            "matches": matches,
        }

    except InvalidImageError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except Exception as error:
        import traceback

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="Failed to recognize product",
        ) from error


# Get a list of product SKUs
@app.get("/catalog/skus", include_in_schema=False)
@app.get("/api/recognition/catalog/skus", deprecated=True)
def get_catalog_skus():
    skus = sorted(sku_dir.name for sku_dir in CATALOG_DIR.iterdir() if sku_dir.is_dir())

    return {"count": len(skus), "skus": skus}


# Add a reference image to a product SKU
@app.post("/catalog/{sku}/images", include_in_schema=False)
@app.post("/api/recognition/catalog/{sku}/images", deprecated=True)
def add_catalog_image(sku: str, file: UploadFile = File(...)):
    # TODO: Save the image and update the FAISS index
    return {"status": "todo", "sku": sku}
