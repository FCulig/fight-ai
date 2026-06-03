import cv2
import torch
from ultralytics import YOLO

# Prefer CUDA, fall back to Apple MPS, then CPU.
_DEVICE = (
    "cuda" if torch.cuda.is_available() else
    "mps"  if torch.backends.mps.is_available() else
    "cpu"
)


def process_video(input_path: str) -> dict:
    """
    Run YOLO detection on the video.

    Returns the detection dict in-memory:
        {"fps": float, "frames": [{"frame": N, "detections": [...]}]}

    No file is written to disk.
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {input_path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()

    print(f"Detected fps: {fps:.2f}")
    model   = YOLO("./video_processing/weights.pt")
    results = model.predict(
        source=input_path, conf=0.25, save=False,
        stream=True, device=_DEVICE, batch=16,
    )
    return _build_detection_dict(results, fps)


def _build_detection_dict(results, fps: float) -> dict:
    frames      = []
    frame_count = 0

    for i, result in enumerate(results):
        frame_count = i + 1
        frame_data  = {"frame": frame_count, "detections": []}

        for box in result.boxes:
            frame_data["detections"].append({
                "class_id":   int(box.cls[0]),
                "confidence": float(box.conf[0]),
                "bbox_xyxy":  box.xyxy[0].tolist(),
            })

        frames.append(frame_data)

    print(f"Processed {frame_count} frames  (fps={fps:.2f})")
    return {"fps": fps, "frames": frames}
