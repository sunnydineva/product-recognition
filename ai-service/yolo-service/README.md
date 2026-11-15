## Product Enrollment

The YOLO service includes a product enrollment workflow that allows users to register new products using a mobile phone camera.

### Architecture

```mermaid

flowchart LR
    subgraph EN["Product Enrollment"]
        direction TB
        A["Phone + SKU"] --> B["OpenCV Cropping"]
        B --> C["Select & Approve"]
        C --> D["DINOv2"]
    end

    subgraph RE["Checkout Recognition"]
        direction TB
        E["Checkout Camera"] --> F["YOLO + ByteTrack"]
        F --> G["Best Product Crop"]
        G --> H["DINOv2"]
    end

    D --> DB[("PostgreSQL + pgvector")]
    DB --> S["Similarity Search"]
    H --> S
    S --> SKU["SKU → Java Backend"]
```

## Object Detection and Tracking

The YOLO service detects and tracks objects in images and videos using YOLO11s and ByteTrack.

Its primary purpose is to locate products at the checkout, extract product crops, and eventually send them to DINOv2 for recognition.
### Detection and Tracking Pipeline
```mermaid
flowchart LR
    A["Image / Video"] --> B["YOLO11s"]
    B --> C["Object Detection"]
    C --> D["ByteTrack"]
    D --> E["Object Cropping"]
    E --> F["BestCropSaver"]
    F -.-> G["DINOv2 Encoder"]
    G -.-> H["pgvector Search"]
    H -.-> I["Recognized SKU"]
```

### Implementation

The enrollment functionality is implemented in the `enrollment/` package:

| File | Responsibility |
|---|---|
| `api.py` | FastAPI endpoints for detection and tracking |
| `detection/crop.py` | Extract object crops from bounding boxes |
| `detection/best_crop.py` | Save the best-quality crop for each tracked object |
| `routes.py` | FastAPI endpoints for preview and approval |
| `video.py` | Extract frames from uploaded videos |
| `localization.py` | Locate and crop products using OpenCV |
| `selection.py` | Score crops and select diverse images |
| `sessions.py` | Manage temporary enrollment sessions |
| `encoding.py` | Convert selected images into DINOv2 embeddings, if added |
| `static/enroll.html` | Mobile-friendly enrollment interface |
| `static/enroll.js` | Camera recording, preview, selection and approval |

### API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/enroll` | Open the enrollment interface |
| POST | `/api/products/preview` | Process video and return selected product crops |
| POST | `/api/products/approve` | Validate selected images against the enrollment session |
| POST | `/detect` | Detect objects in a single image |
| POST | `/track` | Track objects and extract crops from an image |
| POST | `/track-video` | Track objects in video and save the best crop per track |
| GET | `/health` | Check service health |
| GET | `/yolo-names` | Return YOLO model class names |

### Current Status

**Implemented:**
- YOLO11s object detection
- ByteTrack object tracking
- Bounding box extraction
- Object cropping
- Best-crop selection per tracked object in uploaded videos

**Planned:**
- Send selected product crops to DINOv2
- Search stored embeddings using pgvector
- Resolve recognized products to SKU
- Integrate recognition results with the Java backend

Temporary enrollment sessions expire after 30 minutes. Session metadata is currently stored in process memory, so sessions do not survive an application restart.


## Product Enrollment

The YOLO service includes a product enrollment workflow that allows users to register new products using a mobile phone camera.

### Enrollment Pipeline

```mermaid
flowchart LR
    A["Barcode / SKU"] --> B["12-second Video"]
    B --> C["Frame Extraction"]
    C --> D["OpenCV Localization"]
    D --> E["Crop Selection"]
    E --> F["User Approval"]
    F --> G["DINOv2 Embeddings"]
    G --> H[("PostgreSQL + pgvector")]
```

### Implementation

The enrollment functionality is implemented in the `enrollment/` package:

| File | Responsibility |
|---|---|
| `routes.py` | FastAPI endpoints for preview and approval |
| `video.py` | Extract frames from uploaded videos |
| `localization.py` | Locate and crop products using OpenCV |
| `selection.py` | Score crops and select diverse images |
| `sessions.py` | Manage temporary enrollment sessions |
| `encoding.py` | Convert selected images into DINOv2 embeddings (planned integration) |
| `static/enroll.html` | Mobile-friendly enrollment interface |
| `static/enroll.js` | Camera recording, preview, selection and approval |

### API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/enroll` | Open the enrollment interface |
| POST | `/api/products/preview` | Process video and return selected product crops |
| POST | `/api/products/approve` | Validate selected images against the enrollment session |

### Model Training

The YOLO11s model can be fine-tuned using a custom annotated dataset.

Start training:

```bash
python train.py
```

Current training dataset configuration:

```text
dataset/merilka-50ml/data.yaml
```

Training generates model weights:

- `best.pt` — Best model checkpoint based on validation performance
- `last.pt` — Model checkpoint from the final training epoch

### Run Inference

Test the fine-tuned model using the YOLO command-line interface:

```bash
yolo predict \
  model=runs/detect/runs/products_v1-5/weights/best.pt \
  source=dataset/merilka-50ml/images/val/5.jpg \
  conf=0.25 \
  save=True
```

The prediction output includes detected product classes, bounding boxes, and confidence scores.

### Model Limitations

The initial model was trained using a very small dataset and is intended for technical validation.

Additional annotated images and testing on unseen products are required before using the model in a production warehouse environment.

### Current Status

**Implemented and tested:**

- Mobile camera recording
- 12-second video capture
- Video frame extraction using OpenCV
- OpenCV-based product localization
- Crop quality scoring and diverse image selection
- Temporary enrollment session storage
- User preview and manual image selection
- Approval validation API
- DINOv2 encoding tested independently with a real product crop (384-dimensional embedding)

**In progress:**

- Integration of DINOv2 encoding into the enrollment approval API
- Product and embedding persistence in PostgreSQL using pgvector

**Planned:**

- Improvements to product localization and crop selection
- Product similarity search using stored embeddings

### Temporary Sessions

Enrollment previews are stored in temporary sessions.

- Each session contains selected product images and their identifiers.
- Users can review and approve images before enrollment.
- Sessions expire after 30 minutes.
- Session metadata is currently stored in process memory.
- Sessions do not survive an application restart.

Currently, the approval endpoint validates the selected images but does not yet save products or embeddings to the database.
