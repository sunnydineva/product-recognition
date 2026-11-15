
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class LocalizedProduct:
    crop: np.ndarray
    bbox: tuple[int, int, int, int]
    score: float


def localize_product(
    frame: np.ndarray,
) -> LocalizedProduct | None:
    """
    Detect a single prominent, centered product.

    bbox format: (x1, y1, x2, y2)
    Returns None when no reliable candidate is found.
    """

    if frame is None or frame.ndim != 3:
        return None

    height, width = frame.shape[:2]

    if height < 100 or width < 100:
        return None

    # Resize only for contour detection.
    scale = min(1.0, 640.0 / max(width, height))

    small = cv2.resize(
        frame,
        None,
        fx=scale,
        fy=scale,
        interpolation=cv2.INTER_AREA,
    )

    small_h, small_w = small.shape[:2]

    gray = cv2.cvtColor(
        small,
        cv2.COLOR_BGR2GRAY,
    )

    blurred = cv2.GaussianBlur(
        gray,
        (5, 5),
        0,
    )

    edges = cv2.Canny(
        blurred,
        50,
        150,
    )

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (7, 7),
    )

    closed = cv2.morphologyEx(
        edges,
        cv2.MORPH_CLOSE,
        kernel,
    )

    contours, _ = cv2.findContours(
        closed,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    frame_area = small_w * small_h
    center_x = small_w / 2.0
    center_y = small_h / 2.0

    candidates = []

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)

        area_ratio = (w * h) / frame_area

        # Reject very small or almost full-frame boxes.
        if area_ratio < 0.04 or area_ratio > 0.80:
            continue

        # Reject contours touching the image border.
        margin = 3

        if (
            x <= margin
            or y <= margin
            or x + w >= small_w - margin
            or y + h >= small_h - margin
        ):
            continue

        box_center_x = x + w / 2.0
        box_center_y = y + h / 2.0

        normalized_distance = np.sqrt(
            ((box_center_x - center_x) / center_x) ** 2
            + ((box_center_y - center_y) / center_y) ** 2
        )

        # Prefer candidates close to image center.
        center_score = max(
            0.0,
            1.0 - normalized_distance,
        )

        # Prefer substantial but not oversized objects.
        area_score = min(
            area_ratio / 0.30,
            1.0,
        )

        score = (
            0.65 * center_score
            + 0.35 * area_score
        )

        if center_score < 0.35:
            continue

        candidates.append(
            (score, x, y, w, h)
        )

    if not candidates:
        return None

    candidates.sort(reverse=True)

    # Reject similarly strong candidates: the scene may
    # contain multiple objects rather than one product.
    if len(candidates) > 1:
        best_score = candidates[0][0]
        second_score = candidates[1][0]

        if best_score - second_score < 0.08:
            return None

    score, x, y, w, h = candidates[0]

    # Map bounding box to original resolution.
    x1 = round(x / scale)
    y1 = round(y / scale)
    x2 = round((x + w) / scale)
    y2 = round((y + h) / scale)

    # Add 5% padding around the detected product.
    padding_x = round((x2 - x1) * 0.05)
    padding_y = round((y2 - y1) * 0.05)

    x1 = max(0, x1 - padding_x)
    y1 = max(0, y1 - padding_y)
    x2 = min(width, x2 + padding_x)
    y2 = min(height, y2 + padding_y)

    if x2 <= x1 or y2 <= y1:
        return None

    crop = frame[y1:y2, x1:x2].copy()

    return LocalizedProduct(
        crop=crop,
        bbox=(x1, y1, x2, y2),
        score=float(score),
    )
