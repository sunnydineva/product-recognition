import cv2


def crop_object(image, bbox):
    height, width = image.shape[:2]

    x1, y1, x2, y2 = map(int, bbox)

    x1 = max(0, min(x1, width))
    x2 = max(0, min(x2, width))
    y1 = max(0, min(y1, height))
    y2 = max(0, min(y2, height))

    if x2 <= x1 or y2 <= y1:
        return None

    return image[y1:y2, x1:x2].copy()