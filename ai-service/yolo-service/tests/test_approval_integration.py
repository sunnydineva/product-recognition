import os
import uuid
from pathlib import Path

import cv2
import httpx
import pytest
import psycopg

from enrollment.sessions import create_preview_session


IMAGE_DIR = Path("/tmp/product-enrollment-sessions/47eabc070eeb420fb2c0f06658cbbf0b")

IMAGE_IDS = [
    "1dba49e37e3b4ee881c7b13206f06710",
    "baee1ede3dbf4d17bd4ecc87ea485f31",
]


@pytest.mark.asyncio
async def test_approve_saves_embeddings():
    sku = f"TEST-{uuid.uuid4().hex[:8]}"

    crops = []

    for image_id in IMAGE_IDS:
        image = cv2.imread(str(IMAGE_DIR / f"{image_id}.png"))

        assert image is not None, f"Image not found: {image_id}"

        crops.append((0, image))

    session = create_preview_session(
        sku=sku,
        crops=crops,
    )

    from api import app

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/products/approve",
            json={
                "session_id": session.session_id,
                "image_ids": [image.image_id for image in session.images],
            },
        )

    assert response.status_code == 200, response.text

    result = response.json()

    assert result["status"] == "saved"
    assert result["saved_to_database"] is True
    assert result["approved_count"] == 2
    assert result["sku"] == sku
    assert all(item["embedding_dimension"] == 384 for item in result["embeddings"])

    # Verify that embeddings were persisted in PostgreSQL.
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*), MIN(vector_dims(pe.embedding)),
                       MAX(vector_dims(pe.embedding))
                FROM product_embeddings pe
                JOIN products p ON p.id = pe.product_id
                WHERE p.sku = %s
                """,
                (sku,),
            )

            count, min_dimensions, max_dimensions = cursor.fetchone()

    assert count == 2
    assert min_dimensions == 384
    assert max_dimensions == 384
