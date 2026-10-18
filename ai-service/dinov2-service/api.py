from fastapi import FastAPI, UploadFile, File, HTTPException

from dinov2_encoder import get_encoder, InvalidImageError

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/encode")
def encode_image(file: UploadFile = File(...)):
    try:
        image_bytes = file.file.read()

        encoder = get_encoder()
        embedding = encoder.encode(image_bytes)

        return {
            "embedding_dimension": len(embedding),
            "embedding": embedding.tolist()
        }

    except InvalidImageError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )