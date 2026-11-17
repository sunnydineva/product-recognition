import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
from ultralytics import YOLO

from detection.best_crop import BestCropSaver
from detection.recognition import recognize_crop
from detection.preview import save_preview, clear_preview

logger = logging.getLogger(__name__)


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

    # One recognition request at a time, without blocking the camera.
    recognition_worker = ThreadPoolExecutor(max_workers=1)

    # Keep the latest best crop for each track.
    pending_crops: dict[int, bytes] = {}
    submitted_tracks: set[int] = set()

    # Tracks currently visible in the frame.
    active_tracks: set[int] = set()

    # Track how long an object has been missing.
    missing_frames: dict[int, int] = {}

    # Number of frames before a track is considered finished.
    max_missing_frames = 30

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

            current_tracks: set[int] = set()

            for box in results[0].boxes:
                if box.id is None:
                    continue

                track_id = int(box.id.item())
                class_id = int(box.cls.item())
                class_name = model.names[class_id]

                if class_name in ("person", "tv"):
                    continue

                current_tracks.add(track_id)

                bbox = box.xyxy[0].tolist()

                # Update the best crop for this track.
                crop_path = crop_saver.save_if_better(
                    frame,
                    bbox,
                    track_id,
                )

                if crop_path is not None:
                    try:
                        pending_crops[track_id] = Path(crop_path).read_bytes()
                    except OSError as error:
                        logger.error(
                            "Cannot read crop for track %s: %s",
                            track_id,
                            error,
                        )

            # Detect tracks that have disappeared.
            for track_id in active_tracks - current_tracks:
                missing_frames[track_id] = missing_frames.get(track_id, 0) + 1

                if missing_frames[track_id] >= max_missing_frames:
                    image_bytes = pending_crops.pop(track_id, None)

                    if image_bytes is not None and track_id not in submitted_tracks:
                        recognition_worker.submit(
                            recognize_crop,
                            image_bytes,
                            track_id,
                        )
                        submitted_tracks.add(track_id)

                    missing_frames.pop(track_id, None)

            # Reset missing counter for visible tracks.
            for track_id in current_tracks:
                missing_frames.pop(track_id, None)

            # Keep unfinished tracks in the active set.
            active_tracks = current_tracks | set(missing_frames)

            annotated_frame = results[0].plot()
            save_preview(annotated_frame)

            cv2.imshow(
                "AI Product Recognition - Live Camera",
                annotated_frame,
            )

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except KeyboardInterrupt:
        logger.info("Live camera stopped.")

    finally:
        # Submit remaining tracks before shutdown.
        for track_id, image_bytes in pending_crops.items():
            if track_id not in submitted_tracks:
                recognition_worker.submit(
                    recognize_crop,
                    image_bytes,
                    track_id,
                )

        cap.release()
        cv2.destroyAllWindows()
        recognition_worker.shutdown(wait=True)
