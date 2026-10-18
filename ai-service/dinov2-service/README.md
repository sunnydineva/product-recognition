# DINOv2 product recognition service

Planned pipeline: cropped product image → DINOv2 embedding → FAISS similarity
search → product SKU. Encoding is implemented; indexing and recognition are next.

## Image embeddings

Install dependencies from `ai-service/`:

```bash
.venv/bin/python -m pip install -r dinov2-service/requirements.txt
```

From code running inside `dinov2-service/`:

```python
from dinov2_encoder import get_encoder, InvalidImageError

encoder = get_encoder()
try:
    embedding = encoder.encode("catalog/SKU_001/001.jpg")
except InvalidImageError as error:
    print(error)
```

`encode` accepts an image path or raw upload bytes. It handles JPEG and PNG,
converts images to RGB, and applies EXIF orientation before the model's image
processor. Invalid, unreadable, unsupported, or excessively large images raise
`InvalidImageError` so a future API can return a client error.

The default `facebook/dinov2-small` model runs on CPU in evaluation and inference
mode. The final CLS token produces a contiguous, L2-normalized `float32` vector
of shape `(384,)`, suitable for cosine search using FAISS inner products.
Use `get_encoder()` to reuse one model per process, even with concurrent first
calls. First use downloads pretrained weights from Hugging Face; subsequent
starts use its local cache. Model loading failures propagate separately from
image errors. Multiple server workers each hold their own model copy.

Run offline contract tests from `ai-service/` after installing dependencies:

```bash
.venv/bin/python -m unittest discover -s dinov2-service/tests
```

## Product catalog

Each immediate subdirectory of `catalog/` represents one product SKU. Add your
own reference photos to these directories:

```text
catalog/
├── SKU_001/
│   ├── 001.jpg
│   └── 002.jpg
└── SKU_002/
    ├── 001.jpg
    └── 002.jpg
```

`SKU_001` and `SKU_002` are empty example folders, not actual products. The image
names above are examples; no images are included. Rename or replace the folders
with your real SKU identifiers. `.gitkeep` files only preserve empty directories.

- Use a unique, stable folder name for each SKU; add more folders as the catalog
  grows to 100+ products.
- Put multiple reference images of the same product directly in its SKU folder.
- Include different angles and realistic lighting, with the product sharp and
  tightly cropped, similar to the crops produced by the YOLO service.
- Keep different product variants in separate folders when they have different
  SKUs. Do not mix several products in a reference image.
- Prefer JPEG or PNG images. Actual decoding and validation will be implemented
- Prefer JPEG or PNG images. Actual decoding and validation will be implemented
- Use JPEG or PNG images; the encoder validates and decodes their contents.

Reference images remain local and are ignored by Git. Documentation and the
empty example folders are tracked. Generated FAISS indexes are also ignored.
