import cv2
from ultralytics import YOLO
from detection.best_crop import BestCropSaver


def main():
    model = YOLO("models/yolo11s.pt")
    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("Cannot open camera.")
        return

    crop_saver = BestCropSaver()

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
                    crop_saver.save_if_better(frame, bbox, track_id)

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


if __name__ == "__main__":
    main()
