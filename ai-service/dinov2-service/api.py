from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from build_index import build_index as rebuild_catalog_index
from dinov2_encoder import get_encoder, InvalidImageError
from recognition.database import find_similar_products

from faiss_index import FaissIndex


CATALOG_DIR = Path(__file__).resolve().parent / "catalog"
INDEX_DIR = Path(__file__).resolve().parent / "index_data"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the saved index when the API starts
    app.state.product_index = FaissIndex.load(INDEX_DIR)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


# Generate an embedding from the uploaded image
@app.post("/encode")
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
@app.post("/recognize")
def recognize(file: UploadFile = File(...)):
    try:
        image_bytes = file.file.read()

        encoder = get_encoder()
        embedding = encoder.encode(image_bytes)

        matches = find_similar_products(
            embedding.tolist(),
            limit=5,
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
@app.get("/catalog/skus")
def get_catalog_skus():
    skus = sorted(sku_dir.name for sku_dir in CATALOG_DIR.iterdir() if sku_dir.is_dir())

    return {"count": len(skus), "skus": skus}


# Add a reference image to a product SKU
@app.post("/catalog/{sku}/images")
def add_catalog_image(sku: str, file: UploadFile = File(...)):
    # TODO: Save the image and update the FAISS index
    return {"status": "todo", "sku": sku}


# Rebuild the FAISS index from catalog images
@app.post("/catalog/rebuild", deprecated=True)
def rebuild_catalog():
    product_index = rebuild_catalog_index()

    # Replace the active index after rebuilding
    app.state.product_index = product_index

    return {"status": "ok", "indexed_images": product_index.index.ntotal}
