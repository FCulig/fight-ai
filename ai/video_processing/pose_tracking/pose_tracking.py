import cv2
import numpy as np
import torch
from scipy.optimize import linear_sum_assignment
from ultralytics import YOLO
from fight_processing.fight_processing_util import compute_iou

# Prefer CUDA, fall back to Apple MPS, then CPU.
_DEVICE = (
    "cuda" if torch.cuda.is_available() else
    "mps"  if torch.backends.mps.is_available() else
    "cpu"
)

# Raised from 0.1: at 0.1, two overlapping fighter boxes in a clinch could
# both greedily match the same pose box (both being "close enough"), giving
# red and blue the same skeleton — torso distance 0, contact gate trivially
# satisfied, identical velocities. See POSE_IOU_FLOOR below for the other
# half of the fix: one-to-one assignment makes that structurally impossible
# regardless of the floor.
POSE_IOU_FLOOR   = 0.5
POSE_BATCH_SIZE  = 16
LOG_INTERVAL     = 50   # log every N batches


def track_poses(
    track_data: dict,
    video_path: str | None = None,
) -> dict:
    """
    Run pose estimation on every fighter detection.

    Args:
        track_data: In-memory track dict produced by track_fighters()
                    (or loaded from a --track-file dev override).
        video_path: Path to the source .mp4. When supplied, frames are read
                    directly from the video (no frames/ directory needed).
                    Falls back to cv2.imread(image_name) when None.

    Returns:
        Pose dict in-memory — same structure as track_data but with
        keypoints added to each detection.
        No file is written to disk.
    """
    import copy
    data   = copy.deepcopy(track_data)
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

        batch_results = model(images, device=_DEVICE, verbose=False)

        for result, frame_idx in zip(batch_results, valid_indices):
            frame = batch_frames[frame_idx]

            if result.keypoints is None or len(result.keypoints.xy) == 0:
                continue

            pose_boxes = result.boxes.xyxy.cpu().numpy()      # (N, 4)
            pose_kps   = result.keypoints.data.cpu().numpy()  # (N, 17, 3) — [x, y, conf]

            dets = frame["detections"]
            n_dets, n_poses = len(dets), len(pose_boxes)
            if n_dets and n_poses:
                # One-to-one assignment, not greedy argmax-IoU: this is what
                # makes it structurally impossible for two fighter boxes to
                # be assigned the same pose box, rather than merely unlikely.
                size = max(n_dets, n_poses)
                cost = np.full((size, size), 1.0)  # 1 - iou; unmatchable pairs stay at max cost
                for i, det in enumerate(dets):
                    for j, pose_box in enumerate(pose_boxes):
                        cost[i, j] = 1.0 - compute_iou(det["bbox_xyxy"], pose_box.tolist())

                row_ind, col_ind = linear_sum_assignment(cost)
                for r, c in zip(row_ind, col_ind):
                    if r >= n_dets or c >= n_poses:
                        continue
                    if 1.0 - cost[r, c] >= POSE_IOU_FLOOR:
                        dets[r]["keypoints"] = pose_kps[c].tolist()

        if (batch_idx + 1) % LOG_INTERVAL == 0:
            done = min(batch_start + POSE_BATCH_SIZE, total)
            print(f"  Pose: {done}/{total} frames ({100*done/total:.1f}%)")

    if cap:
        cap.release()

    print("Pose tracking complete")
    return data
