from pathlib import Path

from dotenv import load_dotenv

# Load shared configuration before imports that read environment variables.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from ultralytics import YOLO
import numpy as np
import cv2
from enrollment.routes import router as enrollment_router
from detection.crop import crop_object
from detection.best_crop import (
    BestCropSaver,
)  # нова функционалност трябва да избира до 10 различни качествени изображения, затова не трябва директно да използва същата логика за избор и запис.
from camera_control.router import router as camera_router
import os
import tempfile

app = FastAPI(
    title="Product Enrollment API — YOLO",
    description=(
        "API for product enrollment using YOLO. "
        "Handles product detection and preparation of visual data "
        "for the product recognition system."
    ),
    version="1.0.0",
    docs_url="/yolo/docs",
    openapi_url="/yolo/openapi.json",
    redoc_url="/yolo/redoc",
    swagger_ui_oauth2_redirect_url="/yolo/docs/oauth2-redirect",
)
app.include_router(enrollment_router)
app.include_router(camera_router)

modelYolo = YOLO("models/yolo11s.pt")


@app.get("/openapi.json", include_in_schema=False)
def legacy_openapi():
    return app.openapi()


@app.get("/docs", include_in_schema=False)
def legacy_docs():
    return get_swagger_ui_html(openapi_url=app.openapi_url, title=app.title)


@app.get("/redoc", include_in_schema=False)
def legacy_redoc():
    return get_redoc_html(openapi_url=app.openapi_url, title=app.title)


@app.get("/docs/oauth2-redirect", include_in_schema=False)
def legacy_oauth_redirect():
    return get_swagger_ui_oauth2_redirect_html()


async def read_image(file: UploadFile):
    data = await file.read()

    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)

    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    return image


# Detects objects in a single image without tracking.
@app.post("/detect", include_in_schema=False)
@app.post("/api/yolo/detect", tags=["Detection"], summary="Детекция на обекти в едно изображение",
          description="Приема multipart file и връща detections с клас, confidence и bounding box. "
                      "Не проследява обекти, не определя SKU чрез DINOv2 и не записва продукт.")
async def detect(file: UploadFile):
    image = await read_image(file)

    results = modelYolo(image)

    detections = []

    for box in results[0].boxes:
        class_id = int(box.cls.item())

        detections.append(
            {
                "class_id": class_id,
                "class_name": modelYolo.names[class_id],
                "confidence": float(box.conf.item()),
                "bbox": box.xyxy[0].tolist(),
            }
        )

    return {"detections": detections}


# Detects and tracks objects across consecutive video frames,
# assigning persistent track IDs using ByteTrack.
@app.post("/track", include_in_schema=False)
@app.post("/api/yolo/track", tags=["Detection"], summary="Проследяване на обекти между последователни кадри",
          description="Приема един кадър като multipart file. Използва YOLO и ByteTrack с persist=True "
                      "и връща tracks с track_id, клас, confidence и bbox. Състоянието на tracker-а "
                      "се споделя от модела между заявките; това не е отделна сесия на клиент. "
                      "Не извършва DINOv2 разпознаване или запис на продукт.")
async def track(file: UploadFile):
    image = await read_image(file)

    results = modelYolo.track(image, tracker="bytetrack.yaml", persist=True)

    tracks = []

    for box in results[0].boxes:
        track_id = int(box.id.item()) if box.id is not None else None

        bbox = box.xyxy[0].tolist()

        # Crop the detected object from the original image
        crop = crop_object(image, bbox)

        if crop is None:
            continue

        tracks.append(
            {
                "track_id": track_id,
                "class_id": int(box.cls.item()),
                "class_name": modelYolo.names[int(box.cls.item())],
                "confidence": float(box.conf.item()),
                "bbox": box.xyxy[0].tolist(),
            }
        )

        # Later: send crop to DINOv2
        # embedding = dinov2_client.embed(crop)

    return {"tracks": tracks}


@app.post("/track-video", include_in_schema=False)
@app.post("/api/yolo/track-video", tags=["Detection"], summary="Проследяване на обекти във видео",
          description="Приема multipart file с AVI, MP4 или WebM видео, нулира tracker-а и връща "
                      "total_frames и tracks по кадри. Запазва избрани качествени crops чрез "
                      "BestCropSaver; не е enrollment approval и не записва embeddings в базата. "
                      "Временният входен видеофайл се изтрива след обработката.")
async def track_video(file: UploadFile):
    suffix = os.path.splitext(file.filename or "")[1].lower()

    if suffix not in (".avi", ".mp4", ".webm"):
        raise HTTPException(
            status_code=400, detail="Only AVI, MP4 and WebM videos are supported"
        )

    video_path = None
    cap = None

    crop_saver = BestCropSaver()

    try:
        # Save the uploaded video to a temporary file
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
            video_path = temp_file.name

            while chunk := await file.read(1024 * 1024):
                temp_file.write(chunk)

        cap = cv2.VideoCapture(video_path)

        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Cannot open video")

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
                frame, tracker="bytetrack.yaml", persist=True, verbose=False
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

                tracks.append(
                    {
                        "track_id": track_id,
                        "class_id": class_id,
                        "class_name": class_name,
                        "confidence": float(box.conf.item()),
                        "bbox": bbox,
                    }
                )

            frames.append({"frame": frame_number, "tracks": tracks})

        if frame_number == 0:
            raise HTTPException(
                status_code=400, detail="Video contains no readable frames"
            )

        return {"total_frames": frame_number, "frames": frames}

    finally:
        if cap is not None:
            cap.release()

        if video_path is not None and os.path.exists(video_path):
            os.remove(video_path)


@app.get("/health", include_in_schema=False)
@app.get("/api/yolo/health", tags=["Health"], summary="Проверка дали YOLO API работи",
         description="Връща status=ok. Не проверява камерата, PostgreSQL, Kafka или DINOv2.")
def health():
    return {"status": "ok"}


@app.get("/yolo-names", include_in_schema=False)
@app.get("/api/yolo/names", tags=["Detection"], summary="Класове, познати на YOLO модела",
         description="Връща речник names: ID на клас → име. Това са общи детекционни класове, "
                     "не SKU или списък на записаните в AI базата продукти.")
def names():
    print(modelYolo.names)
    return {"names": modelYolo.names}
