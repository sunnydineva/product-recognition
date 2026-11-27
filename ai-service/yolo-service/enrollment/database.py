# INSERT Persist products and their embeddings in PostgreSQL using pgvector.

import os

import psycopg

import logging

logger = logging.getLogger(__name__)


def save_product_embeddings(
    sku: str,
    embeddings: list[tuple[str, list[float]]],
    name: str | None = None,
    note: str | None = None,
) -> None:
    try:
        database_url = os.environ["DATABASE_URL"]

        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                # COALESCE keeps existing hints when a client omits metadata.
                cur.execute(
                    """
                    INSERT INTO products (sku, name, note)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (sku)
                    DO UPDATE SET
                        name = COALESCE(EXCLUDED.name, products.name),
                        note = COALESCE(EXCLUDED.note, products.note)
                    RETURNING id
                    """,
                    (sku, name, note),
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


def count_product_embeddings(sku: str) -> int:
    """Return the number of stored embeddings for the given SKU."""
    try:
        database_url = os.environ["DATABASE_URL"]

        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM product_embeddings pe
                    JOIN products p ON p.id = pe.product_id
                    WHERE p.sku = %s
                    """,
                    (sku,),
                )

                row = cur.fetchone()

        return int(row[0]) if row is not None else 0

    except Exception:
        logger.exception("Failed to count embeddings for SKU %s", sku)
        raise
