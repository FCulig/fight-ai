"""
Offline box smoothing and gap fill over tracked fighter boxes.

`track_fighters()` emits the raw detector box on every matched frame and
nothing at all on a frame the detector missed, so the boxes reaching the
annotation overlay jitter in position and size and blink out on dropped
detections.  Both are worst during a clinch, where heavy mutual occlusion is
exactly where the detector's box extent is least certain.

This is a post-process over the finished track dict rather than a change to
FighterTracker.  Because the pipeline is offline the whole sequence is
available at once, so the filter can be zero-phase — centred on each frame,
introducing no lag — which a causal online filter inside the tracker could not
be.  Boxes and skeletons both arrive from the XL pose model already paired, so
smoothing moves a box without any risk of detaching it from its skeleton.

Three passes per track, in order:

  1. Gap fill — a frame inside a track segment with no box gets one linearly
     interpolated from the bracketing observations, marked `interpolated: True`
     with `confidence: None` (there was no detection to be confident about).
     Holes longer than BOX_GAP_FILL_MAX_SECS are not bridged; they split the
     track instead, because slot ids are reused after a prune and bridging one
     would slide a box between two unrelated positions.

  2. Median prefilter over (cx, cy, w, h).  Rejects the wild box outright —
     the one that briefly engulfs both fighters or collapses onto a limb.
     Savitzky-Golay alone cannot: being a least-squares fit it drags the curve
     toward an outlier, smearing a 2-frame blow-up across ~10 frames.

  3. Savitzky-Golay over (cx, cy, w, h).  Centre and size are smoothed as
     separate series so position jitter and extent jitter are decoupled: a box
     that sits correctly but breathes in size gets settled without being
     dragged off the fighter.

Boxes are never clamped to frame bounds — a fighter really does leave frame at
the cage edge, and a clamped box would misreport their extent.
"""

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import savgol_filter

from models.constants import (
    BOX_GAP_FILL_MAX_SECS,
    BOX_MEDIAN_WINDOW_SECS,
    BOX_SMOOTHING_POLYORDER,
    BOX_SMOOTHING_WINDOW_SECS,
)


def _to_cwh(bbox: list) -> list:
    x1, y1, x2, y2 = bbox
    return [(x1 + x2) / 2.0, (y1 + y2) / 2.0, x2 - x1, y2 - y1]


def _to_xyxy(cwh) -> list:
    cx, cy, w, h = cwh
    return [cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0]


def _collect_tracks(frames: list) -> dict[int, dict[int, dict]]:
    """Index every detection by track id, then by position in `frames`."""
    tracks: dict[int, dict[int, dict]] = {}
    for idx, frame in enumerate(frames):
        for det in frame.get("detections", []):
            tid = det.get("class_id")
            if tid is None or len(det.get("bbox_xyxy") or []) != 4:
                continue
            tracks.setdefault(tid, {})[idx] = det
    return tracks


def _segment(indices: list[int], max_gap: int) -> list[list[int]]:
    """Split sorted frame indices into runs separated by more than max_gap."""
    segments: list[list[int]] = []
    current = [indices[0]]
    for prev, cur in zip(indices, indices[1:]):
        if cur - prev > max_gap:
            segments.append(current)
            current = []
        current.append(cur)
    segments.append(current)
    return segments


def _densify(by_index: dict[int, dict], seg: list[int]):
    """Linearly interpolate (cx, cy, w, h) across every frame the segment spans."""
    dense_idx = np.arange(seg[0], seg[-1] + 1)
    observed  = np.array([_to_cwh(by_index[i]["bbox_xyxy"]) for i in seg], dtype=float)
    dense     = np.empty((dense_idx.size, 4), dtype=float)
    for k in range(4):
        dense[:, k] = np.interp(dense_idx, seg, observed[:, k])
    return dense_idx, dense


def _median(dense: np.ndarray, window: int) -> np.ndarray:
    """Reject outlier boxes. mode='nearest' — zero-padded edges would drag the
    first and last boxes of a segment toward the origin."""
    win = min(window, len(dense))
    if win % 2 == 0:
        win -= 1
    if win < 3:
        return dense
    return median_filter(dense, size=(win, 1), mode="nearest")


def _smooth(dense: np.ndarray, window: int, polyorder: int) -> np.ndarray:
    """Zero-phase Savitzky-Golay along the time axis; pass through if too short."""
    win = min(window, len(dense))
    if win % 2 == 0:
        win -= 1
    if win <= polyorder:
        return dense
    return savgol_filter(dense, win, polyorder, axis=0)


def smooth_track_boxes(track_data: dict) -> dict:
    """
    Gap-fill and smooth every track's boxes in place.

    Mutates and returns `track_data` — the dicts are one entry per video frame
    and a full fight is large enough that a deep copy is not worth it.  Boxes
    added by gap fill carry `interpolated: True` and `confidence: None`; boxes
    that came from a real detection keep their confidence and are only moved.

    Args:
        track_data: {"fps": float, "frames": [{"image_name", "detections"}]}
                    as built by track_fighters().

    Returns:
        The same dict, with bbox_xyxy smoothed and gap-fill detections inserted.
    """
    frames = track_data.get("frames") or []
    if not frames:
        return track_data

    fps       = track_data.get("fps") or 50.0
    window    = max(3, round(fps * BOX_SMOOTHING_WINDOW_SECS))
    if window % 2 == 0:
        window += 1
    med_win   = max(3, round(fps * BOX_MEDIAN_WINDOW_SECS))
    if med_win % 2 == 0:
        med_win += 1
    max_gap   = max(1, round(fps * BOX_GAP_FILL_MAX_SECS))
    polyorder = BOX_SMOOTHING_POLYORDER

    tracks     = _collect_tracks(frames)
    n_filled   = 0
    n_segments = 0

    for tid, by_index in tracks.items():
        for seg in _segment(sorted(by_index), max_gap):
            if len(seg) < 2:
                continue          # a lone box has nothing to interpolate or fit

            n_segments += 1
            dense_idx, dense = _densify(by_index, seg)
            dense = _median(dense, med_win)
            dense = _smooth(dense, window, polyorder)

            for pos, frame_idx in enumerate(dense_idx):
                bbox = _to_xyxy(dense[pos])
                det  = by_index.get(int(frame_idx))
                if det is not None:
                    det["bbox_xyxy"] = bbox
                    continue

                # keypoints stay None: this box was interpolated between two
                # observations, and there is no honest skeleton to invent for
                # it.  Downstream stages already treat missing keypoints as
                # "unusable this frame" rather than as zeros.
                frames[int(frame_idx)]["detections"].append({
                    "bbox_xyxy":    bbox,
                    "confidence":   None,
                    "class_id":     tid,
                    "keypoints":    None,
                    "interpolated": True,
                })
                n_filled += 1

    print(
        f"Box smoothing complete — {n_segments} track segments smoothed "
        f"(median {med_win}, savgol {window} frames), {n_filled} boxes gap-filled"
    )
    return track_data
