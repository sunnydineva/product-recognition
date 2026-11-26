import os
from pathlib import Path

import httpx


DINOV2_URL = os.getenv(
    "DINOV2_URL",
    "http://127.0.0.1:18102",
)


async def encode_image(image_path: Path) -> list[float]:
    image_bytes = image_path.read_bytes()

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{DINOV2_URL.rstrip('/')}/api/recognition/encode",
            files={
                "file": (
                    image_path.name,
                    image_bytes,
                    "image/png",
                )
            },
        )

        response.raise_for_status()

    result = response.json()
    embedding = result["embedding"]

    if len(embedding) != 384:
        raise ValueError("Unexpected embedding dimension")

    return embedding
