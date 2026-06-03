import copy

import cv2
import numpy as np

from models.constants import (
    TAPE_PATCH_HALF,
    WRIST_EDGE_MARGIN,
    TAPE_MIN_SATURATION,
    TAPE_MIN_VALUE,
    RED_HUE_HIGH1,
    RED_HUE_LOW2,
    BLUE_HUE_LOW,
    BLUE_HUE_HIGH,
    CORNER_MIN_TAPE_SAMPLES,
)

# COCO keypoint index pairs: (wrist, elbow) for left and right arms
_WRIST_PAIRS = [(9, 7), (10, 8)]


def _patch_half(kp: list, wrist_idx: int, elbow_idx: int) -> int:
    """Scale crop half-side by forearm length when elbow is visible."""
    wx, wy = kp[wrist_idx][0], kp[wrist_idx][1]
    ex, ey = kp[elbow_idx][0], kp[elbow_idx][1]
    if ex == 0 and ey == 0:
        return TAPE_PATCH_HALF
    forearm = ((wx - ex) ** 2 + (wy - ey) ** 2) ** 0.5
    # Glove tape occupies roughly 0.35× forearm length
    scaled = int(forearm * 0.35)
    return max(TAPE_PATCH_HALF // 2, min(TAPE_PATCH_HALF * 2, scaled))


def _sample_tape(frame_bgr: np.ndarray, kp: list, h: int, w: int) -> tuple[int, int]:
    """
    Count red and blue HSV pixels around both wrists.
    Returns (red_pixels, blue_pixels).
    """
    red_total  = 0
    blue_total = 0

    for wrist_idx, elbow_idx in _WRIST_PAIRS:
        wx, wy = kp[wrist_idx][0], kp[wrist_idx][1]

        if wx == 0 and wy == 0:
            continue
        if (wx < WRIST_EDGE_MARGIN or wx > w - WRIST_EDGE_MARGIN or
                wy < WRIST_EDGE_MARGIN or wy > h - WRIST_EDGE_MARGIN):
            continue

        half = _patch_half(kp, wrist_idx, elbow_idx)
        x1 = max(0, int(wx) - half)
        y1 = max(0, int(wy) - half)
        x2 = min(w, int(wx) + half)
        y2 = min(h, int(wy) + half)

        if x2 <= x1 or y2 <= y1:
            continue

        patch = frame_bgr[y1:y2, x1:x2]
        if patch.size == 0:
            continue

        hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        hue = hsv[:, :, 0]
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]

        quality    = (sat >= TAPE_MIN_SATURATION) & (val >= TAPE_MIN_VALUE)
        red_mask   = ((hue <= RED_HUE_HIGH1) | (hue >= RED_HUE_LOW2)) & quality
        blue_mask  = (hue >= BLUE_HUE_LOW) & (hue <= BLUE_HUE_HIGH) & quality

        red_total  += int(red_mask.sum())
        blue_total += int(blue_mask.sum())

    return red_total, blue_total


def assign_corners(pose_data: dict, video_path: str) -> dict:
    """
    Determine red/blue corner for each provisional track_id (0/1) and rewrite
    class_id in pose_data so that red=0, blue=1 matches the competition convention.

    Strategy:
      1. Read the video once sequentially, sample glove-tape HSV colour around
         each wrist keypoint (COCO kp 9/10) per track.
      2. Aggregate red vs blue pixel counts per track over the whole fight.
      3. The track with more net-red tape → red corner (class_id 0).
      4. Fallback when tape evidence is thin: majority vote of the original
         YOLO model class stored in the 'model_class_id' field set by the
         tracking step.

    Args:
        pose_data:  In-memory pose dict from track_poses().  Detections have
                    provisional class_id (0/1) and 17-point COCO keypoints.
        video_path: Source video — read sequentially, no seeking.

    Returns:
        Deep copy of pose_data with class_id rewritten to final corner labels.
    """
    data   = copy.deepcopy(pose_data)
    frames = data["frames"]
    total  = len(frames)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    red_scores  = {0: 0, 1: 0}
    blue_scores = {0: 0, 1: 0}
    # model_votes[track_id][original_yolo_class] = count
    model_votes: dict[int, dict[int, int]] = {0: {0: 0, 1: 0}, 1: {0: 0, 1: 0}}

    for idx, frame in enumerate(frames):
        fighter_dets = [
            d for d in frame.get("detections", [])
            if d.get("class_id") in (0, 1)
        ]

        if fighter_dets:
            ret, frame_bgr = cap.read()
            frame_bgr = frame_bgr if ret else None
        else:
            cap.grab()
            frame_bgr = None

        if frame_bgr is None:
            continue

        for det in fighter_dets:
            track_id = det["class_id"]

            orig = det.get("model_class_id")
            if orig in (0, 1):
                model_votes[track_id][orig] += 1

            kp = det.get("keypoints")
            if not kp or len(kp) < 11:
                continue

            red_px, blue_px = _sample_tape(frame_bgr, kp, frame_h, frame_w)
            red_scores[track_id]  += red_px
            blue_scores[track_id] += blue_px

        if (idx + 1) % 500 == 0:
            print(f"  Corner assignment: {idx + 1}/{total} frames sampled")

    cap.release()

    # ------------------------------------------------------------------
    # Decide corner map
    # ------------------------------------------------------------------
    total_samples = sum(red_scores.values()) + sum(blue_scores.values())
    print(f"Corner assignment — total tape pixels sampled: {total_samples}")
    print(f"  Track 0: red={red_scores[0]}  blue={blue_scores[0]}")
    print(f"  Track 1: red={red_scores[1]}  blue={blue_scores[1]}")

    if total_samples >= CORNER_MIN_TAPE_SAMPLES:
        net = {t: red_scores[t] - blue_scores[t] for t in (0, 1)}
        corner_map = {0: 0, 1: 1} if net[0] >= net[1] else {0: 1, 1: 0}
        print(f"  Decision: tape vote → {corner_map}")
    else:
        print(
            f"  WARNING: insufficient tape samples ({total_samples} < "
            f"{CORNER_MIN_TAPE_SAMPLES}) — falling back to model class votes"
        )
        corner_map = {}
        for track_id in (0, 1):
            votes  = model_votes[track_id]
            winner = max(votes, key=votes.get) if any(votes.values()) else track_id
            corner_map[track_id] = winner

        # Ensure mutual exclusion after the vote
        if corner_map.get(0) == corner_map.get(1):
            print("  WARNING: model vote tie — using identity mapping as last resort")
            corner_map = {0: 0, 1: 1}

        print(f"  Decision: model vote → {corner_map}")

    # ------------------------------------------------------------------
    # Rewrite class_id throughout pose_data
    # ------------------------------------------------------------------
    swaps = 0
    for frame in data["frames"]:
        for det in frame.get("detections", []):
            old_id = det.get("class_id")
            if old_id in corner_map:
                new_id = corner_map[old_id]
                if new_id != old_id:
                    swaps += 1
                det["class_id"] = new_id

    print(f"  Remapped {swaps} detections to final red/blue corners")

    # ------------------------------------------------------------------
    # Invariant check: no frame should have two fighters with the same id
    # ------------------------------------------------------------------
    violations = 0
    for frame in data["frames"]:
        ids = [
            d["class_id"] for d in frame.get("detections", [])
            if d.get("class_id") in (0, 1)
        ]
        if len(ids) == 2 and ids[0] == ids[1]:
            violations += 1
    if violations:
        print(f"  WARNING: {violations} frame(s) still have duplicate corner ids")
    else:
        print("  Invariant OK: no duplicate corner ids in any frame")

    return data
