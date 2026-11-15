
from enrollment.video import extract_frames, VideoProcessingError


VIDEO_PATH = "test_video.mp4"


try:
    frames = extract_frames(VIDEO_PATH)

    print(f"Extracted frames: {len(frames)}")

    for index, frame in enumerate(frames):
        print(
            f"Frame {index + 1}: "
            f"{frame.timestamp_ms} ms, "
            f"shape={frame.image.shape}"
        )

except VideoProcessingError as exc:
    print(f"Video processing failed: {exc}")
