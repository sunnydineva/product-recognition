import asyncio
from pathlib import Path

from enrollment.dinov2_client import encode_image
from enrollment.database import save_product_embeddings


SKU = "123456789"

IMAGE_DIR = Path("/tmp/product-enrollment-sessions/47eabc070eeb420fb2c0f06658cbbf0b")

IMAGE_IDS = [
    "1dba49e37e3b4ee881c7b13206f06710",
    "baee1ede3dbf4d17bd4ecc87ea485f31",
]


async def main():
    embeddings = []

    for image_id in IMAGE_IDS:
        image_path = IMAGE_DIR / f"{image_id}.png"

        embedding = await encode_image(image_path)

        embeddings.append((image_id, embedding))
        print(f"Encoded {image_id}: {len(embedding)} dimensions")

    save_product_embeddings(SKU, embeddings)

    print(f"Saved {len(embeddings)} embeddings for SKU {SKU}")


if __name__ == "__main__":
    asyncio.run(main())
