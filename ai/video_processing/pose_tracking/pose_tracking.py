import json
import cv2
from ultralytics import YOLO
from fight_processing.fight_processing_util import compute_iou

IOU_MATCH_THRESHOLD = 0.1
POSE_BATCH_SIZE = 16

def track_poses(reid_json_path: str, output_json_path: str = "runs/pose_results.json"):
    data = json.load(open(reid_json_path, "r"))
    frames = data["frames"]
    model = YOLO("yolo26x-pose.pt")

    for detection in (d for frame in frames for d in frame["detections"]):
        detection["keypoints"] = None

    for batch_start in range(0, len(frames), POSE_BATCH_SIZE):
        batch_frames = frames[batch_start:batch_start + POSE_BATCH_SIZE]

        images = []
        valid_indices = []
        for i, frame in enumerate(batch_frames):
            image = cv2.imread(frame["image_name"])
            if image is None:
                print(f"Error: Could not load image from {frame['image_name']}")
                continue
            images.append(image)
            valid_indices.append(i)

        if not images:
            continue

        batch_results = model(images, device='cuda', verbose=False)

        for result, frame_idx in zip(batch_results, valid_indices):
            frame = batch_frames[frame_idx]

            if result.keypoints is None or len(result.keypoints.xy) == 0:
                continue

            pose_boxes = result.boxes.xyxy.numpy()   # shape (N, 4)
            pose_kps   = result.keypoints.xy.numpy() # shape (N, 17, 2)

            for detection in frame["detections"]:
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