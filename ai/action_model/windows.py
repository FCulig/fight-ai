"""Pose-window construction shared by training (dataset.py, from Postgres)
and the pipeline (inference.py, from the in-memory pose dict) — one
implementation, so a model never sees differently-built windows at
inference than it was trained on.

A sample is one fighter ("attacker") at one moment, with the opponent's
skeleton alongside for context:

    x: (IN_CHANNELS, TOTAL_STEPS) float32
       channels = [attacker 17x(x,y,conf), attacker present,
                   opponent 17x(x,y,conf), opponent present]

Coordinates are centred on the attacker's torso at the centre frame, divided
by the attacker's body scale there, and mirrored so the opponent is always to
the attacker's right. Mirroring swaps COCO left/right joints too, which keeps
the pose physically valid and leaves every label unchanged — the families are
hand-agnostic (both hooks are `hook`; jab/cross are lead/rear).
"""

from dataclasses import dataclass

import numpy as np

from models.constants import KEYPOINT_MIN_CONFIDENCE
from models.geometry import get_fighter_scale, get_torso_rectangle

from .config import (
    COORD_CLIP, FLIP_PAIRS, IN_CHANNELS, JITTER_STEPS, N_JOINTS,
    PERSON_CHANNELS, SAMPLE_HZ, WINDOW_STEPS,
)

# Stored windows carry JITTER_STEPS extra samples each side (training shifts
# the centre); the model itself always sees the centre WINDOW_STEPS.
TOTAL_STEPS = WINDOW_STEPS + 2 * JITTER_STEPS


@dataclass
class Track:
    """One corner's skeletons, dense-indexed by frame number."""
    present: np.ndarray    # (max_frame + 1,) bool
    kps: np.ndarray        # (max_frame + 1, 17, 3) float32
    boxes: np.ndarray      # (max_frame + 1, 4) float32


def empty_tracks(max_frame: int) -> dict[int, Track]:
    return {
        corner: Track(
            present=np.zeros(max_frame + 1, bool),
            kps=np.zeros((max_frame + 1, N_JOINTS, 3), np.float32),
            boxes=np.zeros((max_frame + 1, 4), np.float32),
        )
        for corner in (0, 1)
    }


def set_frame(tracks: dict[int, Track], frame: int, corner: int, keypoints, box) -> None:
    """Record one fighter's skeleton; silently ignores a missing/malformed one
    (a box with a JSON-null skeleton is real data loss upstream, not an error)."""
    if keypoints is None or corner not in tracks:
        return
    kp = np.asarray(keypoints, np.float32)
    if kp.shape != (N_JOINTS, 3):
        return
    t = tracks[corner]
    t.present[frame] = True
    t.kps[frame] = kp
    t.boxes[frame] = box


def centre_crop(x: np.ndarray) -> np.ndarray:
    """(..., TOTAL_STEPS) -> (..., WINDOW_STEPS), the model's input length."""
    return x[..., JITTER_STEPS:JITTER_STEPS + WINDOW_STEPS]


def _anchor(track: Track, frame: int):
    """(centre_xy, scale) of a fighter at one frame, or None if absent."""
    if not track.present[frame]:
        return None
    kp = track.kps[frame]
    x1, y1, x2, y2 = track.boxes[frame]
    rect = get_torso_rectangle(kp)
    centre = ((rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2) if rect else ((x1 + x2) / 2, (y1 + y2) / 2)
    scale = get_fighter_scale(kp)
    if scale is None:
        # Torso unusable (crouched, occluded): a third of box height is
        # roughly the torso length on a standing fighter.
        scale = max((y2 - y1) / 3.0, 10.0)
    return np.array(centre, np.float32), float(scale)


def _window_frames(centre: int, fps: int, n_frames: int) -> np.ndarray:
    half = (TOTAL_STEPS - 1) / 2
    offsets = (np.arange(TOTAL_STEPS) - half) / SAMPLE_HZ
    frames = np.rint(centre + offsets * fps).astype(np.int64)
    return np.clip(frames, 0, n_frames - 1)


def _person_channels(track: Track, frames: np.ndarray, origin, scale, flip) -> np.ndarray:
    present = track.present[frames]
    kp = track.kps[frames].copy()                                  # (T, 17, 3)
    if flip:
        for a, b in FLIP_PAIRS:
            kp[:, [a, b]] = kp[:, [b, a]]
    xy = (kp[..., :2] - origin) / scale
    if flip:
        xy[..., 0] = -xy[..., 0]
    conf = kp[..., 2]
    # An unconfident joint's coordinate is a guess; keep its confidence as
    # a signal but zero the position so it can't masquerade as motion.
    xy[conf < KEYPOINT_MIN_CONFIDENCE] = 0.0
    xy = np.clip(xy, -COORD_CLIP, COORD_CLIP)
    feats = np.concatenate([xy, conf[..., None]], axis=-1)       # (T, 17, 3)
    feats[~present] = 0.0
    out = np.concatenate([feats.reshape(len(frames), -1), present[:, None].astype(np.float32)], axis=1)
    return out.T                                                   # (PERSON_CHANNELS, T)


def build_window(tracks: dict[int, Track], fps: int, frame: int, corner: int):
    """The sample for `corner` at `frame`, or None when that fighter has no
    skeleton at the centre frame (nothing to normalise against)."""
    att, opp = tracks[corner], tracks[1 - corner]
    n = len(att.present)
    if frame >= n:
        return None
    anchor = _anchor(att, frame)
    if anchor is None:
        return None
    origin, scale = anchor

    frames = _window_frames(frame, fps, n)
    # Face the attacker toward +x. Prefer the opponent at the centre frame,
    # else the nearest frame in the window that has them.
    flip = False
    opp_frames = [frame] + sorted(frames, key=lambda f: abs(f - frame))
    for f in opp_frames:
        opp_anchor = _anchor(opp, f)
        if opp_anchor is not None:
            flip = bool(opp_anchor[0][0] < origin[0])
            break

    x = np.concatenate([
        _person_channels(att, frames, origin, scale, flip),
        _person_channels(opp, frames, origin, scale, flip),
    ], axis=0)
    assert x.shape == (IN_CHANNELS, TOTAL_STEPS), x.shape
    assert PERSON_CHANNELS * 2 == IN_CHANNELS
    return x
