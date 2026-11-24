import os
import uuid
from pathlib import Path
from dotenv import load_dotenv

import psycopg
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

SKU = "123456789"
IMAGE_PATH = Path(__file__).parent / "resources" / "test-product.png"
DINO_URL = os.environ["DINOV2_SERVICE_URL"].rstrip("/") + "/encode"


def main():
    database_url = os.environ["DATABASE_URL"]

    with psycopg.connect(database_url) as conn:
        # Skip if the example product already has an embedding.
        existing = conn.execute(
            """
            SELECT 1
            FROM products p
            JOIN product_embeddings pe ON pe.product_id = p.id
            WHERE p.sku = %s
            LIMIT 1
            """,
            (SKU,),
        ).fetchone()

        if existing:
            print(f"Product {SKU} is already seeded.")
            return

        # Generate the embedding using the running DINOv2 service.
        with IMAGE_PATH.open("rb") as image:
            response = requests.post(
                DINO_URL,
                files={"file": image},
                timeout=60,
            )

        response.raise_for_status()
        embedding = response.json()["embedding"]

        if len(embedding) != 384:
            raise ValueError("Expected a 384-dimensional embedding.")

        # Create the product if it does not exist.
        product_id = conn.execute(
            """
            INSERT INTO products (sku)
            VALUES (%s)
            ON CONFLICT (sku)
            DO UPDATE SET sku = EXCLUDED.sku
            RETURNING id
            """,
            (SKU,),
        ).fetchone()[0]

        # Save the example embedding.
        conn.execute(
            """
            INSERT INTO product_embeddings (
                product_id,
                image_id,
                embedding
            )
            VALUES (%s, %s, %s::vector)
            """,
            (
                product_id,
                uuid.uuid4(),
                str(embedding),
            ),
        )

        print(f"Seeded product {SKU} successfully.")


if __name__ == "__main__":
    main()
