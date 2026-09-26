"""Strike detection with the trained skeleton action model — the pipeline's
only strike detector (replaced the hand-tuned `detect_strikes` rule cascade).

The model scores one fighter at one moment. Detection slides it along every
scanned span for both corners, one window per sample step (1/SAMPLE_HZ s),
and turns the resulting strike-probability curve into discrete events with
non-maximum suppression: a peak at or above STRIKE_PROB_THRESHOLD becomes a
strike, and suppresses any weaker peak by the same fighter within
STRIKE_NMS_SECS.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from models.constants import STRIKE_NMS_SECS, STRIKE_PROB_THRESHOLD

from . import config
from .config import CLASSES, SAMPLE_HZ, TARGETS
from .model import ActionNet
from .windows import Track, build_window, centre_crop, empty_tracks, set_frame

WEIGHTS_PATH = Path(__file__).resolve().parent / "weights" / "strike_model.pt"
_BATCH = 512


@dataclass
class DetectedStrike:
    frame: int
    corner: int        # 0=red, 1=blue — the attacker
    family: str        # one of CLASSES[1:]
    target: str        # one of TARGETS
    prob: float        # 1 - P(none) at the peak


def load_model(path: Path = WEIGHTS_PATH, device: str = "cpu") -> ActionNet:
    """Loads a checkpoint written by `python -m action_model.train`, refusing
    one built for a different window/taxonomy contract — its input tensor
    would have a different meaning even when the shape happens to match."""
    ckpt = torch.load(path, map_location=device, weights_only=False)
    current = {k: getattr(config, k) for k in dir(config) if k.isupper()}
    saved = {k: tuple(v) if isinstance(v, list) else v for k, v in ckpt["config"].items()}
    mismatched = sorted(k for k in current if saved.get(k) != current[k])
    if mismatched:
        raise ValueError(f"{path} was trained with a different action_model/config.py "
                         f"({', '.join(mismatched)}) — retrain it")
    model = ActionNet().to(device)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    return model


def tracks_from_pose_data(pose_data: dict) -> dict[int, Track]:
    """Pose dict (assign_corners output) -> dense per-corner tracks, indexed by
    1-based frame number like everything else the pipeline writes."""
    frames = pose_data["frames"]
    tracks = empty_tracks(len(frames))
    for index, frame in enumerate(frames):
        for d in frame["detections"]:
            bbox = d.get("bbox_xyxy") or []
            if d.get("class_id") in (0, 1) and len(bbox) == 4:
                set_frame(tracks, index + 1, d["class_id"], d.get("keypoints"), bbox)
    return tracks


@torch.no_grad()
def _score(model: ActionNet, windows: list[np.ndarray], device: str):
    fam, tgt = [], []
    for s in range(0, len(windows), _BATCH):
        xb = torch.from_numpy(centre_crop(np.stack(windows[s:s + _BATCH])).copy()).to(device)
        lf, lt = model(xb)
        fam.append(torch.softmax(lf, 1).cpu().numpy())
        tgt.append(torch.softmax(lt, 1).cpu().numpy())
    return np.concatenate(fam), np.concatenate(tgt)


def _peaks(frames: np.ndarray, p_strike: np.ndarray, fps: int,
           threshold: float, nms_secs: float) -> list[int]:
    """Indices of accepted peaks: strongest first, each suppressing any other
    candidate within nms_secs."""
    radius = nms_secs * fps
    accepted: list[int] = []
    for i in np.argsort(-p_strike):
        if p_strike[i] < threshold:
            break
        if all(abs(frames[i] - frames[j]) > radius for j in accepted):
            accepted.append(int(i))
    return sorted(accepted)


def detect_strikes(
    tracks: dict[int, Track],
    fps: int,
    spans: list[tuple[int, int]],
    model: ActionNet,
    device: str = "cpu",
    threshold: float = STRIKE_PROB_THRESHOLD,
    nms_secs: float = STRIKE_NMS_SECS,
) -> list[DetectedStrike]:
    """Every strike the model finds inside `spans` (inclusive frame ranges),
    for both fighters, sorted by frame."""
    step = max(1, round(fps / SAMPLE_HZ))
    n = len(tracks[0].present)
    strikes: list[DetectedStrike] = []
    for start, end in spans:
        centres = np.arange(max(1, start), min(end, n - 1) + 1, step)
        for corner in (0, 1):
            frames, windows = [], []
            for f in centres:
                x = build_window(tracks, fps, int(f), corner)
                if x is not None:
                    frames.append(int(f))
                    windows.append(x)
            if not windows:
                continue
            fam_p, tgt_p = _score(model, windows, device)
            frames_arr = np.array(frames)
            for i in _peaks(frames_arr, 1.0 - fam_p[:, 0], fps, threshold, nms_secs):
                strikes.append(DetectedStrike(
                    frame=frames[i],
                    corner=corner,
                    family=CLASSES[1 + int(np.argmax(fam_p[i, 1:]))],
                    target=TARGETS[int(np.argmax(tgt_p[i]))],
                    prob=float(1.0 - fam_p[i, 0]),
                ))
    strikes.sort(key=lambda s: (s.frame, s.corner))
    return strikes
