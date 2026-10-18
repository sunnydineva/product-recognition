import os
from datetime import datetime

import cv2

from detection.crop import crop_object


class BestCropSaver:
    def __init__(self, output_dir="crops"):
        # Create a unique folder for each camera session or video
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")

        self.output_dir = os.path.join(output_dir, timestamp)
        self.best_scores = {}

    def save_if_better(self, frame, bbox, track_id):
        crop = crop_object(frame, bbox)

        if crop is None:
            return

        # Calculate image sharpness
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        score = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Keep only the sharpest image for each track
        if score <= self.best_scores.get(track_id, -1):
            return

        self.best_scores[track_id] = score

        track_folder = os.path.join(
            self.output_dir, f"track_{track_id}"
        )
        os.makedirs(track_folder, exist_ok=True)

        filename = os.path.join(track_folder, "best.jpg")
        cv2.imwrite(filename, crop)