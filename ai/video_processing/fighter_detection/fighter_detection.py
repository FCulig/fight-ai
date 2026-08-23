"""
Fighter detection: XL pose supplies the geometry, nano supplies the selection.

Replaces the old two-stage `process_video()` -> `track_poses()` split, in which
the nano detector (`weights.pt`, YOLOv8n, 3.0M params, trained at 640px) emitted
the boxes that survived to the database while `yolo26x-pose` ran over every
frame purely to have its keypoints copied across and its own — far better —
boxes thrown away.

Two things were wrong with that:

  1. The kept box came from the weakest model in the pipeline.  Box extent is
     least certain exactly where the nano model is weakest: mutual occlusion in
     a clinch, where it either engulfs both fighters or collapses onto a limb.

  2. The nano box was also the *lookup key* for the keypoints — a pose was
     attached only when it overlapped the nano box by POSE_IOU_FLOOR.  A bad
     nano box therefore did not merely degrade the box, it dropped the skeleton
     entirely, and the row reached `fighter_frames` with a box and no
     keypoints.  Skeletons are the training signal, so that was silent data
     loss concentrated on the hardest frames.

What the nano model is still good for is the one question the pose model cannot
answer: `yolo26x-pose` is COCO person-only, so it detects the referee,
cornermen and cage-side crowd identically to fighters.  Nano is kept solely as
a *mask* answering "which of these people are the fighters".

Its red/blue class head is deliberately ignored — classes 0 and 1 are collapsed
into one "fighter" concept here.  Corner is decided downstream by
`assign_corners()` from glove tape and torso colour, which is a temporally
consistent appearance decision; the detector's per-frame colour guess never was
one, which is why `assign_corners` exists at all.  Ignoring it also sidesteps a
real failure mode: ultralytics NMS is class-aware by default, so a fighter the
model is torn between red and blue on can survive NMS *twice*, as two
overlapping boxes.  Matching one-to-one against pose persons (below) collapses
that pair back onto the single person it always was.

Referee (class 2) is excluded from the mask, so referee persons find no match
and are dropped.

Output shape — one entry per decoded frame, detections capped at
TRACK_MAX_FIGHTERS:

    {"fps": float,
     "frames": [{"frame": int,                    # 1-based
                 "detections": [{"bbox_xyxy": [x1,y1,x2,y2],   # XL pose box
                                 "confidence": float,          # XL person conf
                                 "keypoints": [[x,y,c] * 17]}]}]}

No `class_id` is emitted: identity is FighterTracker's job and corner is
assign_corners'.  A frame with no usable detection still gets an entry with an
empty list, because every downstream stage indexes frames by position.
"""

import cv2
import numpy as np
import torch
from scipy.optimize import linear_sum_assignment
from ultralytics import YOLO

from fight_processing.fight_processing_util import compute_iou
from models.constants import (
    FIGHTER_MASK_CONF,
    FIGHTER_SELECT_IOU_FLOOR,
    POSE_BATCH_SIZE,
    TRACK_MAX_FIGHTERS,
)

# Prefer CUDA, fall back to Apple MPS, then CPU.
_DEVICE = (
    "cuda" if torch.cuda.is_available() else
    "mps"  if torch.backends.mps.is_available() else
    "cpu"
)

_NANO_WEIGHTS = "./video_processing/weights.pt"
_POSE_WEIGHTS = "yolo26x-pose.pt"

# Nano classes 0 and 1 are 'red' and 'blue'.  Both mean "fighter" here and the
# distinction is discarded — see module docstring.  Class 2 (referee) is absent
# on purpose: that is what keeps the referee out of the tracked pair.
_NANO_FIGHTER_CLASSES = {0, 1}

_LOG_INTERVAL = 50   # log every N pose batches


# ---------------------------------------------------------------------------
# Pass 1 — nano fighter mask
# ---------------------------------------------------------------------------

def _fighter_mask(video_path: str) -> list[list[list[float]]]:
    """Per-frame list of boxes marking where the fighters are.

    Only the *regions* are used.  Confidence is not carried forward and the
    red/blue class is discarded, so this is a binary "fighter here" mask, not a
    detection result in its own right.
    """
    model   = YOLO(_NANO_WEIGHTS)
    results = model.predict(
        source=video_path, conf=FIGHTER_MASK_CONF, save=False,
        stream=True, device=_DEVICE, batch=16, verbose=False,
    )

    regions: list[list[list[float]]] = []
    for result in results:
        regions.append([
            box.xyxy[0].tolist()
            for box in result.boxes
            if int(box.cls[0]) in _NANO_FIGHTER_CLASSES
        ])

    n_with = sum(1 for r in regions if r)
    print(f"  Fighter mask: {len(regions)} frames, "
          f"{n_with} with at least one fighter region")
    return regions


# ---------------------------------------------------------------------------
# Pass 2 — XL pose over every frame, fighters selected by the mask
# ---------------------------------------------------------------------------

def _select_fighters(result, regions: list[list[float]]) -> list[dict]:
    """Pick the pose-model persons that land on a fighter mask region.

    Hungarian rather than greedy, and one-to-one: two mask boxes sitting on the
    same fighter (the class-aware-NMS duplicate described in the module
    docstring) cannot both claim that person, so the duplicate finds no partner
    and is dropped instead of manufacturing a phantom second fighter.
    """
    if result.boxes is None or len(result.boxes) == 0 or not regions:
        return []

    pboxes = result.boxes.xyxy.cpu().numpy()
    pconf  = result.boxes.conf.cpu().numpy()
    pkps   = (result.keypoints.data.cpu().numpy()
              if result.keypoints is not None else None)

    n_p, n_r = len(pboxes), len(regions)
    size     = max(n_p, n_r)

    # 1.0 = no overlap; padding rows/cols stay there and are rejected by the
    # IoU floor below rather than by a sentinel.
    cost = np.ones((size, size), dtype=float)
    for i in range(n_p):
        for j in range(n_r):
            cost[i, j] = 1.0 - compute_iou(pboxes[i].tolist(), regions[j])

    row_ind, col_ind = linear_sum_assignment(cost)

    matched: list[tuple[float, int]] = []
    for r, c in zip(row_ind, col_ind):
        if r >= n_p or c >= n_r:
            continue
        if 1.0 - cost[r, c] < FIGHTER_SELECT_IOU_FLOOR:
            continue
        matched.append((float(pconf[r]), int(r)))

    # More mask regions than fighters can survive (a cornerman clipped by a
    # loose nano box).  Keep the most confident persons — there are only ever
    # TRACK_MAX_FIGHTERS of them.
    matched.sort(key=lambda m: m[0], reverse=True)

    return [
        {
            "bbox_xyxy":  pboxes[r].tolist(),
            "confidence": conf,
            "keypoints":  pkps[r].tolist() if pkps is not None else None,
        }
        for conf, r in matched[:TRACK_MAX_FIGHTERS]
    ]


def _pose_and_select(video_path: str, regions: list) -> list[dict]:
    """Run the XL pose model over the video and keep only the fighters."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    model  = YOLO(_POSE_WEIGHTS)
    frames: list[dict] = []
    idx    = 0
    batch_no = 0

    while True:
        images:  list = []
        indices: list[int] = []
        for _ in range(POSE_BATCH_SIZE):
            ret, image = cap.read()
            if not ret:
                break
            images.append(image)
            indices.append(idx)
            idx += 1

        if not images:
            break

        results  = model(images, device=_DEVICE, verbose=False)
        batch_no += 1

        for result, i in zip(results, indices):
            frame_regions = regions[i] if i < len(regions) else []
            frames.append({
                "frame":      i + 1,          # 1-based, matches fighter_frames
                "detections": _select_fighters(result, frame_regions),
            })

        if batch_no % _LOG_INTERVAL == 0:
            print(f"  Pose+select: {idx} frames processed")

    cap.release()
    return frames


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_fighters(video_path: str, on_pose_start=None) -> dict:
    """
    Detect the two fighters on every frame, with boxes and skeletons from the
    XL pose model and fighter-vs-bystander selection from the nano mask.

    Args:
        video_path:    Source video.  Decoded twice — once per model pass —
                       which is what the previous two-stage arrangement cost
                       as well.
        on_pose_start: Optional zero-arg callback fired after the (fast) mask
                       pass and before the (slow) pose pass.  The pipeline uses
                       it to move the fight into its POSE state, so the UI still
                       distinguishes the two halves now that they are one step.

    Returns:
        Detection dict; see module docstring for the exact shape.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()

    print(f"Detected fps: {fps:.2f}")

    print("Running fighter mask (nano) …")
    regions = _fighter_mask(video_path)

    if on_pose_start is not None:
        on_pose_start()

    print("Running pose detection + fighter selection (XL) …")
    frames  = _pose_and_select(video_path, regions)

    n_dets    = sum(len(f["detections"]) for f in frames)
    n_both    = sum(1 for f in frames if len(f["detections"]) == 2)
    n_kps     = sum(1 for f in frames for d in f["detections"]
                    if d.get("keypoints"))
    print(
        f"Detection complete — {len(frames)} frames, {n_dets} fighter "
        f"detections ({n_both} frames with both fighters), "
        f"{n_kps} carrying keypoints"
    )
    return {"fps": fps, "frames": frames}
