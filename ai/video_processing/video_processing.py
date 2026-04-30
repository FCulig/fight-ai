import json
from ultralytics import YOLO

def process_video(input_path: str):
    model = YOLO("./video_processing/weights.pt")
    results = model.predict(source=input_path, conf=0.25, save=False, stream=True, device='cuda', batch=16)
    return save_results_to_json(results)

def save_results_to_json(results):
    output_path = "runs/detection_results.json"
    frame_count = 0

    with open(output_path, "w", encoding="utf-8") as f:
        f.write('{"frames":[\n')
        first_frame = True

        for i, result in enumerate(results):
            frame_count = i + 1
            frame_data = {
                "frame": frame_count,
                "detections": []
            }

            for box in result.boxes:
                detection = {
                    "class_id": int(box.cls[0]),
                    "confidence": float(box.conf[0]),
                    "bbox_xyxy": box.xyxy[0].tolist()
                }
                frame_data["detections"].append(detection)

            if not first_frame:
                f.write(",\n")
            f.write(json.dumps(frame_data))
            first_frame = False

        f.write("\n]}\n")

    print(f"Saved {frame_count} frames to {output_path}")
    return output_path