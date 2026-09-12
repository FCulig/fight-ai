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
be.  Boxes and skeletons both arrive from the XL pose model already paired —
but smoothing moves the box and nothing moves the keypoints, so the pairing is
something this module has to actively preserve rather than something it gets
for free.  Pass 5 is what preserves it.

Five passes per track, in order:

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

  4. Drift check — when the filtered box has been carried off its own
     skeleton, the filtered value is discarded for that frame and the observed
     box is used instead.  See below; this runs before the floor so the floor
     is always applied to a box that belongs to its keypoints.

  5. Skeleton floor — the box is unioned with this frame's own confident
     keypoint hull, so smoothing can settle a box but can never crop it below
     the joints the pose model actually saw.

Step 4 exists because passes 2 and 3 can move a box *off the person it
describes*, which detaches it from its own skeleton.  The filters act on the box
series alone; nothing smooths the keypoints, so any displacement the filter
applies is a displacement between a box and a skeleton that arrived together.
The median prefilter is the sharp edge of this: it exists to overrule a short,
large excursion, and a frame where the tracker briefly put a different person in
this slot *is* such an excursion — so the box gets quietly pulled back onto the
slot's trajectory while the keypoints stay with the person the detector actually
found.  The stored row then shows one fighter's box around another's skeleton,
and it is invisible in the overlay precisely because the box looks right.

Measured on the stored rows of fights 52 and 54: the skeleton's torso centre
falls outside its own box on 585/71,177 (0.82%) and 474/76,606 (0.62%) of rows.
The shape of that population is what decides the repair:

  - It is overwhelmingly **one-sided** — only 23 and 14 of those frames have
    *both* fighters' rows mismatched.  So this is not mostly a clean two-fighter
    identity swap that could be undone by exchanging the two slots' labels;
    exchanging labels would address about 4% of it.
  - Displacements run from marginal to gross: median 0.15 box diagonals outside,
    p90 0.65, max 3.65.
  - Runs are short — 80% and 93% of runs last 1-2 frames, the exact length the
    5-frame median absorbs.

The repair is therefore to **discard the filtered box** on those frames rather
than to try to reconstruct the identity.  The observed box is guaranteed to hold
its own skeleton — they are two outputs of one pose detection — so falling back
to it restores the pairing by construction, for every cause, without this module
having to diagnose which one applied.  It costs smoothing on <1% of frames.

Two things it deliberately does not do.  It does not repair the *identity*: when
the tracker put the wrong person in this slot, the row afterwards holds that
person's box and that person's skeleton, consistently, and still under the wrong
slot id.  That is the tracker's error and it is left where it can be seen —
which is the second point: reverting makes the box jump on the overlay again,
so a labeller watching the fight sees the glitch instead of a plausible-looking
box hiding a mislabelled skeleton.  The root cause is upstream, in how
FighterTracker resolves identity at a camera cut or in a clinch.

Blast radius, replaying the drift predicate over every stored row: 0.56% of
fight 52's rows and 0.43% of fight 54's would be reverted, and everything left
below the threshold is within 0.05 diagonals of its box.  The three fights
processed before this module existed sit at 0.03-0.08%, which is consistent with
smoothing being the cause — though not proof of it, since those fights also
predate the XL-pose box and had their keypoints IoU-matched to their boxes,
which forced an overlap by construction.

Note the drift check and the median prefilter are not in tension: a box that
briefly engulfs both fighters or collapses onto a limb still *contains* its own
skeleton, so it fails no drift test and the median goes on rejecting it as
before.  Only boxes carried off their own person are reverted.

Step 5 exists because passes 2 and 3 cannot tell a *punch* from an *outlier*.
Both are a brief, large excursion in w: an extended arm reaches its apex for
2-4 frames at 50fps, and a 5-frame median filter is built to delete exactly
that.  Measured on fight 52 (DRAGOJEVICvsHONDA_3) before this step existed, a
confident wrist landed outside the stored box on 10.2% of frames, by a mean of
35px and a p90 of 83px — and a wrist moving fast (top decile, i.e. mid-strike)
was 3-4x likelier to be outside than a slow one, 5.9-7.1% vs 1.7%.  The box
was therefore least correct precisely on the frames the whole system exists to
capture.  The floor is the keypoint hull rather than the raw detector box
because the failure mode pass 2 targets — the box that briefly engulfs both
fighters or collapses onto a limb — is a *box* failure, not a skeleton one: the
keypoints still describe one person.  Unioning with the hull therefore restores
real extent without restoring the wild box.  Wrists and ankles are padded
outward by BOX_EXTREMITY_PAD_RATIO of fighter scale, since a glove and a foot
extend well past the joint centre the pose model marks.

Motion blur is a real property of this footage but is *not* what clips the box.
Measured over 4,842 arm-observations straight off DRAGOJEVICvsHONDA_3 with no
pipeline in between: as elbow speed rises the wrist keypoint is lost outright
(confidence < KEYPOINT_MIN_CONFIDENCE) on 26% of the fastest frames versus 11%
at rest, and the hand's image gradient along its direction of travel drops
relative to across it (0.96 → 0.88), which is the signature of a smear.  But the
raw pose box still contained the wrist on 98-100% of frames *in every speed
bin* — flat.  The person box is drawn round the whole silhouette, and the blur
streak is part of that silhouette, so a blurred hand costs the skeleton, not the
box.  Blur therefore explains missing keypoints; it does not explain a box that
stops at the shoulder, and the step-5 floor is aimed at the smoothing instead.

Boxes are never clamped to frame bounds — a fighter really does leave frame at
the cage edge, and a clamped box would misreport their extent.
"""

import numpy as np
from scipy.ndimage import median_filter
from scipy.signal import savgol_filter

from models.constants import (
    BOX_EXTREMITY_PAD_RATIO,
    BOX_HULL_MAX_SCALE_RATIO,
    BOX_SKELETON_DRIFT_RATIO,
    BOX_GAP_FILL_MAX_SECS,
    BOX_MEDIAN_WINDOW_SECS,
    BOX_SMOOTHING_POLYORDER,
    BOX_SMOOTHING_WINDOW_SECS,
    KEYPOINT_MIN_CONFIDENCE,
)
from models.geometry import get_fighter_scale

# COCO wrists and ankles.  The joint the pose model marks is the wrist bone,
# not the front of the glove, and the ankle, not the toe.
_EXTREMITY_INDICES = (9, 10, 15, 16)


def _to_cwh(bbox: list) -> list:
    x1, y1, x2, y2 = bbox
    return [(x1 + x2) / 2.0, (y1 + y2) / 2.0, x2 - x1, y2 - y1]


def _to_xyxy(cwh) -> list:
    cx, cy, w, h = cwh
    return [cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0]


def _keypoint_hull(keypoints) -> list | None:
    """Bounding box of this frame's confident joints, padded at the extremities.

    Returns None when the skeleton cannot be trusted to bound a body: too few
    confident joints, no measurable fighter scale, or a hull far too large to be
    one person (see the gates below).  A hull drawn through one or two joints is
    not a body, and unioning with it would pull the box toward whatever that
    joint happens to be.  The same KEYPOINT_MIN_CONFIDENCE gate the rest of the
    system uses applies here, so an occluded or hallucinated joint cannot
    stretch the box on its own.
    """
    if not keypoints:
        return None

    points = [kp[:2] for kp in keypoints
              if len(kp) > 2 and kp[2] >= KEYPOINT_MIN_CONFIDENCE]
    if len(points) < 4:
        return None

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    hull = [min(xs), min(ys), max(xs), max(ys)]

    # No trustworthy body size means no way to check the hull against one, and
    # this hull is about to become a floor the box cannot go below — so decline
    # rather than floor the box against an unmeasurable skeleton.  Frames whose
    # shoulders are unconfident are already "unusable this frame" everywhere
    # else in the system (see models/geometry.py).
    scale = get_fighter_scale(keypoints)
    if scale is None:
        return None

    # A skeleton whose joints span more than a couple of body heights is not
    # describing one person — it is a pose failure with joints scattered across
    # the frame.  Measured over fights 52 and 54, the hull's long side sits at
    # 2.4 fighter scales in the median and 3.3 at p90 (a body is ~3.3 scales
    # tall, and a fully committed strike reaches past that), but the tail runs
    # to 51.  Flooring a box against one of those would inflate it enormously,
    # so the gate keeps the ~0.9% beyond BOX_HULL_MAX_SCALE_RATIO out.
    if max(hull[2] - hull[0], hull[3] - hull[1]) > BOX_HULL_MAX_SCALE_RATIO * scale:
        return None

    # Pad around the extremities only.  A uniform pad would inflate the box at
    # the head and hips too, where the joint already sits near the silhouette
    # edge; the glove and the foot are the parts that genuinely overhang.
    pad = BOX_EXTREMITY_PAD_RATIO * scale
    for i in _EXTREMITY_INDICES:
        if i >= len(keypoints):
            continue
        kp = keypoints[i]
        if len(kp) <= 2 or kp[2] < KEYPOINT_MIN_CONFIDENCE:
            continue
        hull = [min(hull[0], kp[0] - pad), min(hull[1], kp[1] - pad),
                max(hull[2], kp[0] + pad), max(hull[3], kp[1] + pad)]

    return hull


def _skeleton_drift(bbox: list, keypoints) -> float:
    """How far this skeleton's torso centre lies outside this box, in box
    diagonals.  0.0 means the skeleton sits inside the box it is stored with.

    The torso centre (confident COCO shoulders/hips, the same four joints
    `get_torso_rectangle` uses) is the most reliably detected point on a
    fighter, so it is the right anchor for "is this box still on this person".
    A skeleton too sparse to place a torso centre returns 0.0 — unmeasurable is
    not evidence of drift, and such a frame is already "unusable" downstream.

    Expressed in box diagonals rather than pixels so it means the same thing on
    a close-up and a wide shot, like every other geometric ratio here.
    """
    if not keypoints:
        return 0.0
    pts = [kp[:2] for i, kp in enumerate(keypoints)
           if i in (5, 6, 11, 12) and len(kp) > 2 and kp[2] >= KEYPOINT_MIN_CONFIDENCE]
    if len(pts) < 2:
        return 0.0

    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    dx = max(bbox[0] - cx, cx - bbox[2], 0.0)
    dy = max(bbox[1] - cy, cy - bbox[3], 0.0)
    if dx == 0.0 and dy == 0.0:
        return 0.0

    diag = max(1.0, ((bbox[2] - bbox[0]) ** 2 + (bbox[3] - bbox[1]) ** 2) ** 0.5)
    return (dx * dx + dy * dy) ** 0.5 / diag


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
    n_floored  = 0
    n_reverted = 0
    n_detector_mismatch = 0
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
                    keypoints = det.get("keypoints")

                    # Drift check.  det["bbox_xyxy"] is still the OBSERVED box
                    # at this point — it is only overwritten at the end of this
                    # iteration — and the observed box holds its own skeleton by
                    # construction, both being outputs of one pose detection.
                    # So when the filters have carried the box off its own
                    # person, falling back to the observation restores the
                    # pairing whatever the cause was.  See module docstring.
                    if _skeleton_drift(bbox, keypoints) > BOX_SKELETON_DRIFT_RATIO:
                        bbox = list(det["bbox_xyxy"])
                        n_reverted += 1
                        if _skeleton_drift(bbox, keypoints) > BOX_SKELETON_DRIFT_RATIO:
                            # The detector's own box does not hold its own
                            # skeleton.  Nothing here can fix that; count it so
                            # it stays a number rather than a surprise.
                            n_detector_mismatch += 1

                    # Skeleton floor: settle the box, never crop it below what
                    # the pose model saw on this frame.  A punch is a 2-4 frame
                    # excursion in width and the median prefilter is built to
                    # delete excursions that short — see module docstring.
                    hull = _keypoint_hull(keypoints)
                    if hull is not None:
                        if (hull[0] < bbox[0] or hull[1] < bbox[1]
                                or hull[2] > bbox[2] or hull[3] > bbox[3]):
                            n_floored += 1
                        bbox = [min(bbox[0], hull[0]), min(bbox[1], hull[1]),
                                max(bbox[2], hull[2]), max(bbox[3], hull[3])]
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
        f"(median {med_win}, savgol {window} frames), {n_filled} boxes gap-filled, "
        f"{n_floored} widened to their own skeleton, "
        f"{n_reverted} reverted to the observed box (filter drifted off the skeleton)"
    )
    if n_detector_mismatch:
        # Not this module's doing — the detector emitted a box that does not
        # contain the skeleton it came with.  Worth seeing, not worth failing on.
        print(f"  NOTE: {n_detector_mismatch} box(es) still off their own "
              f"skeleton after reverting — the observed box itself disagrees")
    return track_data
