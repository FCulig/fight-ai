import json
from pathlib import Path

import cv2
from ultralytics import YOLO


def process_video(input_path: str):
    # Detect fps from the source video before running inference
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {input_path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()

    print(f"Detected fps: {fps:.2f}")
    model   = YOLO("./video_processing/weights.pt")
    results = model.predict(
        source=input_path, conf=0.25, save=False,
        stream=True, device='cuda', batch=16,
    )
    return save_results_to_json(results, fps)


def save_results_to_json(results, fps: float):
    output_path = "runs/detection_results.json"
    Path("runs").mkdir(exist_ok=True)
    frame_count = 0

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f'{{"fps": {fps:.6f}, "frames":[\n')
        first_frame = True

        for i, result in enumerate(results):
            frame_count = i + 1
            frame_data  = {"frame": frame_count, "detections": []}

            for box in result.boxes:
                frame_data["detections"].append({
                    "class_id":   int(box.cls[0]),
                    "confidence": float(box.conf[0]),
                    "bbox_xyxy":  box.xyxy[0].tolist(),
                })

            if not first_frame:
                f.write(",\n")
            f.write(json.dumps(frame_data))
            first_frame = False

        f.write("\n]}\n")

    print(f"Saved {frame_count} frames to {output_path}  (fps={fps:.2f})")
    return output_path
