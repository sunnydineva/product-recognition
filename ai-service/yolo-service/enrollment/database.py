# INSERT Persist products and their embeddings in PostgreSQL using pgvector.

import os

import psycopg

import logging

logger = logging.getLogger(__name__)


def save_product_embeddings(
    sku: str,
    embeddings: list[tuple[str, list[float]]],
) -> None:
    try:
        database_url = os.environ["DATABASE_URL"]

        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO products (sku)
                    VALUES (%s)
                    ON CONFLICT (sku)
                    DO UPDATE SET sku = EXCLUDED.sku
                    RETURNING id
                    """,
                    (sku,),
                )

                product_id = cur.fetchone()[0]

                for image_id, embedding in embeddings:
                    if len(embedding) != 384:
                        raise ValueError("Unexpected embedding dimension")

                    vector = "[" + ",".join(map(str, embedding)) + "]"

                    cur.execute(
                        """
                        INSERT INTO product_embeddings (
                            product_id,
                            image_id,
                            embedding
                        )
                        VALUES (%s, %s, %s::vector)
                        ON CONFLICT (image_id)
                        DO NOTHING
                        """,
                        (product_id, image_id, vector),
                    )

            conn.commit()

    except Exception:
        logger.exception("Failed to save embeddings for SKU %s", sku)
        raise
