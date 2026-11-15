import cv2
from ultralytics import YOLO

from detection.best_crop import BestCropSaver


def run_live_camera(
    model: YOLO,
    camera_index: int = 0,
) -> None:
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {camera_index}")

    crop_saver = BestCropSaver()

    # Reset tracking state for this camera session
    model.predictor = None

    try:
        while True:
            success, frame = cap.read()

            if not success:
                break

            results = model.track(
                frame,
                tracker="bytetrack.yaml",
                persist=True,
                verbose=False,
            )

            for box in results[0].boxes:
                if box.id is None:
                    continue

                track_id = int(box.id.item())
                class_id = int(box.cls.item())
                class_name = model.names[class_id]
                bbox = box.xyxy[0].tolist()

                # Skip background objects
                if class_name in ("person", "tv"):
                    continue

                # Keep the best crop for each tracked object
                crop_saver.save_if_better(frame, bbox, track_id)

            annotated_frame = results[0].plot()

            cv2.imshow(
                "AI Product Recognition - Live Camera",
                annotated_frame,
            )

            # Press Q in the camera window to stop
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        print("\nLive camera stopped.")

    finally:
        cap.release()
        cv2.destroyAllWindows()
