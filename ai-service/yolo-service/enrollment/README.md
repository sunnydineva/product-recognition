# Enrollment via Web UI

```mermaid
flowchart LR
    A["Browser: /enroll"] --> B["enroll.html"]
    B --> C["enroll.js"]
    C -->|" POST /api/products/preview "| D["YOLO Enrollment"]
    D -->|" Images + session_id "| C
    C -->|" POST /api/products/approve "| D
    D -->|" One image at a time "| E["DINOv2 /encode"]
    E -->|" 384D embeddings "| D
```

# Enrollment via API Client

The process consists of three steps:

1. POST /api/products/preview — Upload a video and SKU. Returns a session_id and a list of candidate images (image_id).
2. POST /api/products/approve — Submit the session_id and selected image_ids.
3. POST /encode — Automatically called by YOLO Service once per approved image. No manual API call is required.

```mermaid
flowchart LR
    A["API Client"] -->|" 1. POST /api/products/preview "| B["YOLO Service"]
    B -->|" session_id + image_ids "| A
    A -->|" 2. POST /api/products/approve "| B
    B -->|" 3. Automatic per-image encoding "| C["DINOv2 /encode"]
    C -->|" 384D embeddings "| B
    B -->|" status: encoded "| A
```

TODO — Product Enrollment

- [x] Extract frames from uploaded video.
- [x] Detect and crop products using YOLO.
- [x] Select up to 10 high-quality, diverse images.
- [x] Implement Enrollment Preview UI (enroll.html).
- [x] Implement POST /api/products/preview.
- [x] Implement POST /api/products/approve.
- [x] Integrate YOLO Service with DINOv2 /encode.
- [x] Generate 384-dimensional embeddings for approved images.
- [ ] Set up PostgreSQL with pgvector.
- [ ] Create products and product_embeddings tables.
- [ ] Persist SKU and approved image embeddings.
- [ ] Handle duplicate SKU enrollment and re-enrollment.
- [ ] Implement product recognition using vector similarity search.
- [ ] Integrate recognition with the Java Inventory Service.

