import json
import cv2
from ultralytics import YOLO
from fight_processing.fight_processing_util import compute_iou

IOU_MATCH_THRESHOLD = 0.1
POSE_BATCH_SIZE     = 16
LOG_INTERVAL        = 50   # log every N batches


def track_poses(
    reid_json_path: str,
    output_json_path: str = "runs/pose_results.json",
    video_path: str | None = None,
):
    """
    Run pose estimation on every fighter detection.

    Args:
        reid_json_path:    Path to runs/output_reidentification.json.
        output_json_path:  Where to write pose_results.json.
        video_path:        Path to the source .mp4. When supplied, frames are
                           read directly from the video (no frames/ directory).
                           Falls back to cv2.imread(image_name) when None.

    Output:
        Writes pose_results.json with keypoints added to each detection.
    """
    data   = json.load(open(reid_json_path, "r"))
    frames = data["frames"]
    model  = YOLO("yolo26x-pose.pt")
    total  = len(frames)

    cap = None
    if video_path:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {video_path}")
        # Frames are in sequential order — never seek, just read forward.
        print(f"Pose: reading frames sequentially from video: {video_path}")
    else:
        print("Pose: reading frames from frames/ directory")

    # Initialise all keypoints to None
    for detection in (d for frame in frames for d in frame["detections"]):
        detection["keypoints"] = None

    n_batches = (total + POSE_BATCH_SIZE - 1) // POSE_BATCH_SIZE

    for batch_idx, batch_start in enumerate(range(0, total, POSE_BATCH_SIZE)):
        batch_frames = frames[batch_start:batch_start + POSE_BATCH_SIZE]

        images        = []
        valid_indices = []

        for i, frame in enumerate(batch_frames):
            image_name = frame.get("image_name", "")

            if cap is not None:
                ret, image = cap.read()   # sequential — no seeking
                image = image if ret else None
            else:
                image = cv2.imread(image_name)

            if image is None:
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

            pose_boxes = result.boxes.xyxy.cpu().numpy()    # (N, 4)
            pose_kps   = result.keypoints.xy.cpu().numpy()  # (N, 17, 2)

            for detection in frame["detections"]:
                reid_box   = detection["bbox_xyxy"]
                best_iou   = IOU_MATCH_THRESHOLD
                best_index = -1

                for i, pose_box in enumerate(pose_boxes):
                    iou = compute_iou(reid_box, pose_box.tolist())
                    if iou > best_iou:
                        best_iou   = iou
                        best_index = i

                if best_index >= 0:
                    detection["keypoints"] = pose_kps[best_index].tolist()

        if (batch_idx + 1) % LOG_INTERVAL == 0:
            done = min(batch_start + POSE_BATCH_SIZE, total)
            print(f"  Pose: {done}/{total} frames ({100*done/total:.1f}%)")

    if cap:
        cap.release()

    with open(output_json_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Pose tracking complete → {output_json_path}")
