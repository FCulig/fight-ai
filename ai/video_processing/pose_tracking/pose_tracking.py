import json
import cv2
from ultralytics import YOLO
from fight_processing.fight_processing_util import compute_iou

IOU_MATCH_THRESHOLD = 0.1

def track_poses(reid_json_path: str, output_json_path: str = "runs/pose_results.json"):
    data = json.load(open(reid_json_path, "r"))
    frames = data["frames"]
    model = YOLO("yolo26x-pose.pt")

    for frame in frames:
        image_path = frame["image_name"]
        detections = frame["detections"]

        image = cv2.imread(image_path)

        if image is None:
            print(f"Error: Could not load image from {image_path}")
            continue

        # Initialise all detections with no keypoints
        for detection in detections:
            detection["keypoints"] = None

        # Run pose on the full frame — model sees both fighters simultaneously
        results = model(image)

        if not results or results[0].keypoints is None or len(results[0].keypoints.xy) == 0:
            continue

        # Build list of (bbox_xyxy, keypoints) for every skeleton the model found
        pose_boxes = results[0].boxes.xyxy.numpy()   # shape (N, 4)
        pose_kps   = results[0].keypoints.xy.numpy() # shape (N, 17, 2)

        # Match each ReID detection to the best-IoU skeleton
        for detection in detections:
            reid_box = detection["bbox_xyxy"]
            best_iou   = IOU_MATCH_THRESHOLD
            best_index = -1

            for i, pose_box in enumerate(pose_boxes):
                iou = compute_iou(reid_box, pose_box.tolist())
                if iou > best_iou:
                    best_iou   = iou
                    best_index = i

            if best_index >= 0:
                detection["keypoints"] = pose_kps[best_index].tolist()

    with open(output_json_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Pose tracking complete. Results saved to {output_json_path}")