
from dataclasses import dataclass

import cv2
import numpy as np

from enrollment.localization import LocalizedProduct


@dataclass
class CropCandidate:
    timestamp_ms: int
    product: LocalizedProduct


@dataclass
class SelectedCrop:
    timestamp_ms: int
    product: LocalizedProduct
    sharpness: float
    brightness: float
    quality_score: float


def image_features(image: np.ndarray) -> np.ndarray:
    """
    Low-resolution appearance descriptor.
    Used for approximate duplicate detection.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (32, 32))

    features = small.astype(np.float32).flatten()
    features -= features.mean()

    norm = np.linalg.norm(features)

    if norm > 1e-6:
        features /= norm

    return features


def image_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def calculate_quality(image: np.ndarray) -> tuple[float, float, float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    sharpness = float(cv2.Laplacian(
        gray,
        cv2.CV_64F,
    ).var())

    brightness = float(gray.mean())

    # Normalize sharpness approximately to 0..1.
    sharpness_score = min(sharpness / 250.0, 1.0)

    # Prefer moderate lighting.
    brightness_score = max(
        0.0,
        1.0 - abs(brightness - 130.0) / 130.0,
    )

    quality_score = (
        0.75 * sharpness_score
        + 0.25 * brightness_score
    )

    return sharpness, brightness, quality_score


def select_best_crops(
    candidates: list[CropCandidate],
    max_crops: int = 10,
    similarity_threshold: float = 0.94,
    min_time_gap_ms: int = 250,
) -> list[SelectedCrop]:

    if max_crops <= 0:
        return []

    evaluated = []

    for candidate in candidates:
        crop = candidate.product.crop

        if crop is None or crop.size == 0:
            continue

        sharpness, brightness, quality = calculate_quality(crop)

        # Reject extreme lighting.
        if brightness < 25 or brightness > 235:
            continue

        features = image_features(crop)

        evaluated.append((
            quality,
            candidate,
            sharpness,
            brightness,
            features,
        ))

    # Best quality first.
    evaluated.sort(key=lambda item: item[0], reverse=True)

    selected = []
    selected_features = []

    for quality, candidate, sharpness, brightness, features in evaluated:

        if len(selected) >= max_crops:
            break

        too_close_in_time = any(
            abs(candidate.timestamp_ms - item.timestamp_ms)
            < min_time_gap_ms
            for item in selected
        )

        if too_close_in_time:
            continue

        duplicate = any(
            image_similarity(features, previous) > similarity_threshold
            for previous in selected_features
        )

        if duplicate:
            continue

        selected.append(
            SelectedCrop(
                timestamp_ms=candidate.timestamp_ms,
                product=candidate.product,
                sharpness=sharpness,
                brightness=brightness,
                quality_score=quality,
            )
        )

        selected_features.append(features)

    # Display in chronological order.
    selected.sort(key=lambda item: item.timestamp_ms)

    return selected
