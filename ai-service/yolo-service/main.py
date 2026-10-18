from fastapi import FastAPI, UploadFile, HTTPException
from ultralytics import YOLO
import numpy as np
import cv2
from detection.crop import crop_object
from detection.best_crop import BestCropSaver
import os
import tempfile

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
    image = await read_image(file)

    results = modelYolo(image)

    detections = []

    for box in results[0].boxes:
        class_id = int(box.cls.item())

        detections.append({
            "class_id": class_id,
            "class_name": modelYolo.names[class_id],
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

        bbox = box.xyxy[0].tolist()

        # Crop the detected object from the original image
        crop = crop_object(image, bbox)

        if crop is None:
            continue

        tracks.append({
            "track_id": track_id,
            "class_id": int(box.cls.item()),
            "class_name": modelYolo.names[int(box.cls.item())],
            "confidence": float(box.conf.item()),
            "bbox": box.xyxy[0].tolist()
        })

        # Later: send crop to DINOv2
        # embedding = dinov2_client.embed(crop)

    return {"tracks": tracks}

@app.post("/track-video")
async def track_video(file: UploadFile):
    suffix = os.path.splitext(file.filename or "")[1].lower()

    if suffix not in (".avi", ".mp4", ".webm"):
        raise HTTPException(
            status_code=400,
            detail="Only AVI, MP4 and WebM videos are supported"
        )

    video_path = None
    cap = None

    crop_saver = BestCropSaver()

    try:
        # Save the uploaded video to a temporary file
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False
        ) as temp_file:
            video_path = temp_file.name

            while chunk := await file.read(1024 * 1024):
                temp_file.write(chunk)

        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            raise HTTPException(
                status_code=400,
                detail="Cannot open video"
            )

        # Reset tracking state for each uploaded video
        modelYolo.predictor = None

        frames = []
        frame_number = 0

        while True:
            success, frame = cap.read()

            if not success:
                break

            frame_number += 1

            # Run YOLO detection and ByteTrack tracking
            results = modelYolo.track(
                frame,
                tracker="bytetrack.yaml",
                persist=True,
                verbose=False
            )

            tracks = []

            for box in results[0].boxes:
                if box.id is None:
                    continue

                track_id = int(box.id.item())
                class_id = int(box.cls.item())
                bbox = box.xyxy[0].tolist()
                class_name = modelYolo.names[class_id]

                # Skip background objects
                if class_name in ("person", "tv"):
                    continue

                # Save the sharpest crop for this track
                crop_saver.save_if_better(frame, bbox, track_id)

                tracks.append({
                    "track_id": track_id,
                    "class_id": class_id,
                    "class_name": class_name,
                    "confidence": float(box.conf.item()),
                    "bbox": bbox
                })


            frames.append({
                "frame": frame_number,
                "tracks": tracks
            })

        if frame_number == 0:
            raise HTTPException(
                status_code=400,
                detail="Video contains no readable frames"
            )

        return {
            "total_frames": frame_number,
            "frames": frames
        }

    finally:
        if cap is not None:
            cap.release()

        if video_path is not None and os.path.exists(video_path):
            os.remove(video_path)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/yolo-names")
def names ():
    print(modelYolo.names)
    return {"names": modelYolo.names}
