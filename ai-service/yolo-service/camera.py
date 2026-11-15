from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import time

import cv2
import requests
from ultralytics import YOLO
from detection.best_crop import BestCropSaver


DINOV2_RECOGNIZE_URL = os.getenv(
    "DINOV2_RECOGNIZE_URL", "http://127.0.0.1:18102/recognize"
)


def recognize_crop(image_bytes, track_id):
    """Send a snapshot of the saved crop without blocking camera capture."""
    try:
        response = requests.post(
            DINOV2_RECOGNIZE_URL,
            files={"file": (f"track_{track_id}.jpg", image_bytes, "image/jpeg")},
            timeout=(2, 15),
        )
        response.raise_for_status()
        print(f"DINOv2 | track {track_id}: {response.json()}")
    except (requests.RequestException, ValueError) as error:
        print(f"DINOv2 | track {track_id}: recognition failed: {error}")


def main():
    model = YOLO("models/yolo11s.pt")
    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("Cannot open camera.")
        return

    crop_saver = BestCropSaver()
    recognition_worker = ThreadPoolExecutor(max_workers=1)
    pending_recognition = None
    last_sent = {}

    try:
        while True:
            success, frame = camera.read()

            if not success:
                print("Cannot read camera frame.")
                break

            # Detect and track objects in the current frame
            results = model.track(
                frame,
                tracker="bytetrack.yaml",
                persist=True,
                verbose=False,
                conf=0.25,
            )

            result = results[0]

            if result.boxes is not None:
                for box in result.boxes:
                    if box.id is None:
                        continue

                    track_id = int(box.id.item())
                    class_id = int(box.cls.item())
                    class_name = model.names[class_id]
                    bbox = box.xyxy[0].tolist()

                    # Skip background objects
                    if class_name in ("person", "tv"):
                        continue

                    # Save the sharpest crop for this track
                    crop_path = crop_saver.save_if_better(frame, bbox, track_id)

                    # Bound requests to one in flight and one per track per 2 seconds.
                    now = time.monotonic()
                    if (
                        crop_path is not None
                        and (pending_recognition is None or pending_recognition.done())
                        and now - last_sent.get(track_id, float("-inf")) >= 2
                    ):
                        try:
                            image_bytes = Path(crop_path).read_bytes()
                        except OSError as error:
                            print(f"Cannot read crop for track {track_id}: {error}")
                        else:
                            pending_recognition = recognition_worker.submit(
                                recognize_crop, image_bytes, track_id
                            )
                            last_sent[track_id] = now

                    # Draw bounding box and track ID
                    x1, y1, x2, y2 = map(int, bbox)

                    cv2.rectangle(
                        frame,
                        (x1, y1),
                        (x2, y2),
                        (0, 255, 0),
                        2,
                    )

                    label = f"ID {track_id} | {class_name}"

                    cv2.putText(
                        frame,
                        label,
                        (x1, max(y1 - 10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2,
                    )

            cv2.imshow("YOLO Camera Tracking", frame)

            # Press Q to stop
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        camera.release()
        cv2.destroyAllWindows()
        recognition_worker.shutdown(wait=True, cancel_futures=True)


if __name__ == "__main__":
    main()
