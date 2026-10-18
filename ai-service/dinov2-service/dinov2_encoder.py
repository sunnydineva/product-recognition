"""CPU DINOv2 embeddings shared by catalog indexing and recognition."""

from io import BytesIO
from pathlib import Path
from threading import Lock
import warnings

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
import torch
from transformers import AutoImageProcessor, AutoModel


class InvalidImageError(ValueError):
    """The supplied image cannot be decoded as a supported JPEG or PNG."""


def _read_image(source: str | Path | bytes) -> Image.Image:
    if isinstance(source, bytes):
        source = BytesIO(source)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(source) as image:
                if image.format not in {"JPEG", "PNG"}:
                    raise InvalidImageError("Only JPEG and PNG images are supported.")
                image.load()
                return ImageOps.exif_transpose(image).convert("RGB")
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InvalidImageError(
            "Cannot read image. Provide a valid, readable JPEG or PNG image."
        ) from exc


class DinoV2Encoder:
    """Reuse one instance; each embedding is a unit-length float32 vector."""

    def __init__(self, model_name: str = "facebook/dinov2-small") -> None:
        self.processor = AutoImageProcessor.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to("cpu")
        self.model.eval()
        self.model.requires_grad_(False)
        self.embedding_dim = self.model.config.hidden_size

    @torch.inference_mode()
    def encode(self, source: str | Path | bytes) -> np.ndarray:
        """Encode an image path or upload bytes; invalid images raise InvalidImageError.

        Uses the final CLS token (384 dimensions for dinov2-small). The returned
        contiguous (D,) array can be stacked for FAISS inner-product search.
        """
        image = _read_image(source)
        inputs = self.processor(images=image, return_tensors="pt")
        outputs = self.model(**inputs)
        embedding = outputs.last_hidden_state[0, 0].float()
        norm = torch.linalg.vector_norm(embedding)
        if not torch.isfinite(embedding).all() or not torch.isfinite(norm) or norm <= 0:
            raise RuntimeError("DINOv2 produced an invalid embedding.")
        return np.ascontiguousarray((embedding / norm).cpu().numpy(), dtype=np.float32)


_encoder: DinoV2Encoder | None = None
_encoder_lock = Lock()


def get_encoder() -> DinoV2Encoder:
    """Load the default model once per process, including concurrent first calls."""
    global _encoder
    with _encoder_lock:
        if _encoder is None:
            _encoder = DinoV2Encoder()
        return _encoder
