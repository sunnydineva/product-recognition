from ultralytics import YOLO

from detection.live_camera import run_live_camera


def main():
    model = YOLO("models/yolo11s.pt")

    run_live_camera(model, camera_index=0)


if __name__ == "__main__":
    main()
