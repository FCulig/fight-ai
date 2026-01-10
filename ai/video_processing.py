import json
from ultralytics import YOLO

def process_video(input_path: str):
    model = YOLO("./weights.pt")
    results = model.predict(source=input_path, conf=0.25, save=True)
    return save_results_to_json(results)

def save_results_to_json(results):
    output = []
    for i, result in enumerate(results):
        frame_data = {
            "frame": i + 1,
            "detections": []
        }

        for box in result.boxes:
            detection = {
                "class_id": int(box.cls[0]),
                "confidence": float(box.conf[0]),
                "bbox_xyxy": box.xyxy[0].tolist()
            }
            frame_data["detections"].append(detection)
        output.append(frame_data)
    
    OUTPUT_JSON = "detection_results.json"
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f)

    print(f"Saved {len(output)} frames to {OUTPUT_JSON}")

    # TODO: Write all outputs into a single folder, instead of re-writing each time
    return output