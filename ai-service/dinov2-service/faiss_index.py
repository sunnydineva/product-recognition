import faiss
import json
from pathlib import Path
import numpy as np

# embedding in DINOv2-small.
EMBEDDING_DIMENSION = 384


class FaissIndex:
    def __init__(self):
        # Store normalized embeddings for similarity search
        self.index = faiss.IndexFlatIP(EMBEDDING_DIMENSION)
        self.metadata = []

    # Add an embedding to the existing index
    def add(self, embedding: np.ndarray, sku: str, image_path: str):
        # FAISS expects a 2D float32 array
        vector = np.asarray(embedding, dtype=np.float32).reshape(1, -1)
        self.index.add(vector)

        # Keep product information in the same order as FAISS vectors
        self.metadata.append({
            "sku": sku,
            "image_path": image_path
        })

    def search(self, embedding: np.ndarray, k: int = 3):
        # Find the k most similar embeddings
        vector = np.asarray(embedding, dtype=np.float32).reshape(1, -1)
        similarities, indices = self.index.search(vector, k)

        return similarities, indices

    def save(self, directory: str | Path):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        # Save embeddings and product metadata
        faiss.write_index(self.index, str(directory / "products.faiss"))

        with open(directory / "metadata.json", "w", encoding="utf-8") as file:
            json.dump(self.metadata, file, indent=4)

    # @classmethod
    # def load(cls, directory: str | Path):
    #     directory = Path(directory)
    #
    #     # Load the saved FAISS index and metadata
    #     product_index = cls()
    #
    #     product_index.index = faiss.read_index(
    #         str(directory / "products.faiss")
    #     )
    #
    #     with open(directory / "metadata.json", "r", encoding="utf-8") as file:
    #         product_index.metadata = json.load(file)
    #
    #     if product_index.index.ntotal != len(product_index.metadata):
    #         raise ValueError("FAISS index and metadata have different sizes")
    #
    #     return product_index

    @classmethod
    def load(cls, directory: str | Path):
        directory = Path(directory)

        product_index = cls()

        index_path = directory / "products.faiss"
        metadata_path = directory / "metadata.json"

        # First startup: no saved index yet
        if not index_path.exists() and not metadata_path.exists():
            return product_index

        # Detect incomplete storage
        if not index_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(
                "FAISS index and metadata must both exist"
            )

        product_index.index = faiss.read_index(str(index_path))

        with open(metadata_path, "r", encoding="utf-8") as file:
            product_index.metadata = json.load(file)

        if product_index.index.d != EMBEDDING_DIMENSION:
            raise ValueError("Unexpected FAISS embedding dimension")

        if product_index.index.ntotal != len(product_index.metadata):
            raise ValueError("FAISS index and metadata have different sizes")

        return product_index
