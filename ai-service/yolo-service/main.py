from fastapi import FastAPI, UploadFile, HTTPException
from ultralytics import YOLO
import numpy as np
import cv2

app = FastAPI()

modelYolo = YOLO("models/yolo11s.pt")

async def read_image(file: UploadFile):
    data = await file.read()

    image = cv2.imdecode(
        np.frombuffer(data, np.uint8),
        cv2.IMREAD_COLOR
    )

    if image is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid image"
        )

    return image

# Detects objects in a single image without tracking.
@app.post("/detect")
async def detect(file: UploadFile):
    data = await file.read()

    image = cv2.imdecode(
        np.frombuffer(data, np.uint8),
        cv2.IMREAD_COLOR
    )

    if image is None:
        return {"error": "Invalid image"}

    results = modelYolo(image)

    detections = []

    for box in results[0].boxes:
        detections.append({
            "class_id": int(box.cls.item()),
            "confidence": float(box.conf.item()),
            "bbox": box.xyxy[0].tolist()
        })

    return {"detections": detections}

# Detects and tracks objects across consecutive video frames,
# assigning persistent track IDs using ByteTrack.
@app.post("/track")
async def track(file: UploadFile):
    image = await read_image(file)

    results = modelYolo.track(
        image,
        tracker="bytetrack.yaml",
        persist=True
    )

    tracks = []

    for box in results[0].boxes:
        track_id = (
            int(box.id.item())
            if box.id is not None
            else None
        )

        tracks.append({
            "track_id": track_id,
            "class_id": int(box.cls.item()),
            "confidence": float(box.conf.item()),
            "bbox": box.xyxy[0].tolist()
        })

    return {"tracks": tracks}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/yolo-names")
def names ():
    print(modelYolo.names)
    return {"names": modelYolo.names}
