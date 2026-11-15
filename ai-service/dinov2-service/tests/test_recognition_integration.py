import os
import uuid
import unittest
from pathlib import Path

import psycopg
import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

IMAGE_PATH = PROJECT_ROOT / "dinov2-service/resources/test-product.png"
BASE_URL = os.environ["DINOV2_SERVICE_URL"].rstrip("/")
DATABASE_URL = os.environ["DATABASE_URL"]


class TestRecognitionIntegration(unittest.TestCase):
    def test_recognize_enrolled_product(self):
        sku = f"TEST-RECOGNITION-{uuid.uuid4().hex[:8]}"
        product_id = None

        with psycopg.connect(DATABASE_URL) as conn:
            try:
                # Generate an embedding for the test image.
                with IMAGE_PATH.open("rb") as image:
                    response = requests.post(
                        f"{BASE_URL}/encode",
                        files={"file": image},
                        timeout=60,
                    )

                self.assertEqual(response.status_code, 200)
                embedding = response.json()["embedding"]
                self.assertEqual(len(embedding), 384)

                # Insert the test product into PostgreSQL.
                product_id = conn.execute(
                    """
                    INSERT INTO products (sku)
                    VALUES (%s)
                    RETURNING id
                    """,
                    (sku,),
                ).fetchone()[0]

                conn.execute(
                    """
                    INSERT INTO product_embeddings (
                        product_id, image_id, embedding
                    )
                    VALUES (%s, %s, %s::vector)
                    """,
                    (product_id, uuid.uuid4(), str(embedding)),
                )
                conn.commit()

                # Recognize the same image through the API.
                with IMAGE_PATH.open("rb") as image:
                    response = requests.post(
                        f"{BASE_URL}/recognize",
                        files={"file": image},
                        timeout=60,
                    )

                self.assertEqual(response.status_code, 200)

                result = response.json()
                print(f"\nExpected SKU: {sku}")
                print(f"Recognition result: {result}")
                self.assertEqual(result["status"], "matched")

                matches = [match for match in result["matches"] if match["sku"] == sku]

                self.assertTrue(matches)
                self.assertAlmostEqual(matches[0]["similarity"], 1.0, places=4)

            finally:
                # Remove test data even if an assertion fails.
                if product_id is not None:
                    conn.rollback()
                    conn.execute(
                        "DELETE FROM product_embeddings WHERE product_id = %s",
                        (product_id,),
                    )
                    conn.execute(
                        "DELETE FROM products WHERE id = %s",
                        (product_id,),
                    )
                    conn.commit()


if __name__ == "__main__":
    unittest.main()
