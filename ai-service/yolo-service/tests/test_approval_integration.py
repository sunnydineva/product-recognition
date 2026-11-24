import os
import uuid
import unittest
from pathlib import Path

import cv2
import httpx
import psycopg
from dotenv import load_dotenv

from enrollment.sessions import create_preview_session


PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

IMAGE_DIR = Path("/tmp/product-enrollment-sessions/47eabc070eeb420fb2c0f06658cbbf0b")

IMAGE_IDS = [
    "1dba49e37e3b4ee881c7b13206f06710",
    "baee1ede3dbf4d17bd4ecc87ea485f31",
]


class TestApprovalIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_approve_saves_embeddings(self):
        sku = f"TEST-{uuid.uuid4().hex[:8]}"

        try:
            crops = []

            for image_id in IMAGE_IDS:
                image = cv2.imread(str(IMAGE_DIR / f"{image_id}.png"))
                self.assertIsNotNone(image, f"Image not found: {image_id}")
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

            self.assertEqual(response.status_code, 200, response.text)

            result = response.json()

            self.assertEqual(result["status"], "saved")
            self.assertTrue(result["saved_to_database"])
            self.assertEqual(result["approved_count"], 2)
            self.assertEqual(result["sku"], sku)
            self.assertTrue(
                all(item["embedding_dimension"] == 384 for item in result["embeddings"])
            )

            # Verify that embeddings were persisted in PostgreSQL.
            with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT COUNT(*),
                               MIN(vector_dims(pe.embedding)),
                               MAX(vector_dims(pe.embedding))
                        FROM product_embeddings pe
                        JOIN products p ON p.id = pe.product_id
                        WHERE p.sku = %s
                        """,
                        (sku,),
                    )

                    count, min_dimensions, max_dimensions = cursor.fetchone()

            self.assertEqual(count, 2)
            self.assertEqual(min_dimensions, 384)
            self.assertEqual(max_dimensions, 384)

        finally:
            # Remove the test product and its embeddings.
            with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        DELETE FROM product_embeddings
                        WHERE product_id IN (
                            SELECT id FROM products WHERE sku = %s
                        )
                        """,
                        (sku,),
                    )

                    cursor.execute(
                        "DELETE FROM products WHERE sku = %s",
                        (sku,),
                    )

                conn.commit()


if __name__ == "__main__":
    unittest.main()
