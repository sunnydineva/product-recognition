# SELECT # Find similar products using pgvector cosine similarity.

import math
import os

import psycopg


EMBEDDING_DIMENSION = 384
MAX_RESULTS = 20


def find_similar_products(
    embedding: list[float],
    limit: int = 1,
) -> list[dict]:
    if len(embedding) != EMBEDDING_DIMENSION:
        raise ValueError(
            f"Expected {EMBEDDING_DIMENSION} dimensions, got {len(embedding)}"
        )

    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        for value in embedding
    ):
        raise ValueError("Embedding must contain only finite numbers")

    if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"Limit must be between 1 and {MAX_RESULTS}")

    vector = "[" + ",".join(str(value) for value in embedding) + "]"

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                    SELECT
                        p.sku,
                        MAX(1 - (pe.embedding <=> %s::vector)) AS similarity
                    FROM product_embeddings pe
                    JOIN products p ON p.id = pe.product_id
                    GROUP BY p.sku
                    ORDER BY similarity DESC
                    LIMIT %s
                """,
                (vector, limit),
            )

            rows = cursor.fetchall()

    return [{"sku": sku, "similarity": float(similarity)} for sku, similarity in rows]
