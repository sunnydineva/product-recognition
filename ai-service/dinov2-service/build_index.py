from pathlib import Path

from dinov2_encoder import get_encoder
from faiss_index import FaissIndex


CATALOG_DIR = Path(__file__).resolve().parent / "catalog"

def build_index():
    encoder = get_encoder()
    product_index = FaissIndex()

    for sku_dir in CATALOG_DIR.iterdir():
        if not sku_dir.is_dir():
            continue

        sku = sku_dir.name

        for image_path in sku_dir.iterdir():
            if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                continue

            embedding = encoder.encode(image_path)

            # Add the embedding with its product metadata
            product_index.add(
                embedding=embedding,
                sku=sku,
                image_path=str(image_path)
            )

            print(f"SKU: {sku}, Image: {image_path.name}")

    print(f"Total indexed images: {product_index.index.ntotal}")

    product_index.save(INDEX_DIR)

    return product_index


if __name__ == "__main__":
    build_index()

