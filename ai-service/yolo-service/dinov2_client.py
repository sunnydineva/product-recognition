import requests
import os

DINOV2_URL = os.getenv(
    "DINOV2_RECOGNIZE_URL",
    "http://127.0.0.1:18102/recognize"
)


def recognize_product(image_bytes: bytes):
    response = requests.post(
        DINOV2_URL,
        files={"file": ("crop.jpg", image_bytes, "image/jpeg")},
        timeout=10
    )
    response.raise_for_status()
    return response.json()