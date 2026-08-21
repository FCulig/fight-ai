"""
Shared pure-geometry helpers used by both the corner-assignment stage
(video_processing) and the fight-processing stage.

Kept here to avoid a layering inversion: corner_assignment runs *before*
fight_processing in the pipeline, so it cannot import from fight_processing.

All three functions here return `None` when they don't have enough confident
signal to compute an answer, rather than silently computing on a hallucinated
coordinate. Callers must treat `None` as "unusable this frame" — see the
callers in fight_processing_util.py (`detect_strikes`, `determine_fight_state`,
`is_fighter_grounded`) for the pattern.
"""

import numpy as np

from models.constants import KEYPOINT_MIN_CONFIDENCE, TORSO_SCALE_MIN_RATIO


def _confident(keypoints, idx) -> bool:
    kp = keypoints[idx]
    return len(kp) > 2 and kp[2] >= KEYPOINT_MIN_CONFIDENCE


def get_torso_rectangle(keypoints):
    """Returns (x1, y1, x2, y2) torso rectangle from shoulders and hips
    (COCO keypoints 5, 6, 11, 12), or None when fewer than 2 of the 4 are
    confident — a torso rectangle built mostly from hallucinated joints
    corrupts every distance threshold downstream, since it feeds both
    `calculate_distance_between_fighters` (the state-classifier's primary
    axis) and every contact-gate check in `detect_strikes`."""
    indices = [5, 6, 11, 12]
    valid_points = [keypoints[i][:2] for i in indices if _confident(keypoints, i)]

    if len(valid_points) < 2:
        return None

    points = np.array(valid_points)
    x1 = points[:, 0].min()
    y1 = points[:, 1].min()
    x2 = points[:, 0].max()
    y2 = points[:, 1].max()

    return (x1, y1, x2, y2)


def calculate_distance_between_fighters(rect1, rect2):
    """Distance between two torso rectangles (0 when they overlap), or None
    when either rectangle is unavailable.

    Deliberately does NOT fall back to `inf`: a caller comparing an unknown
    distance against a "far apart" threshold would read "STRIKING" for a
    frame where the truth is "we don't know" — see determine_fight_state's
    None-handling for the fix this return value exists to make possible."""
    if not rect1 or not rect2:
        return None

    x1_min, y1_min, x1_max, y1_max = rect1
    x2_min, y2_min, x2_max, y2_max = rect2

    dx = max(0, max(x1_min, x2_min) - min(x1_max, x2_max))
    dy = max(0, max(y1_min, y2_min) - min(y1_max, y2_max))

    return np.sqrt(dx**2 + dy**2)


def get_fighter_scale(keypoints):
    """Body-size reference in pixels: distance from shoulder midpoint to hip
    midpoint. Falls back to shoulder width when hips are foreshortened or
    unconfident. Returns None when neither signal is usable — this is the
    denominator of every normalised threshold in the system, so a
    hallucinated fallback here would silently rescale the whole strike
    detector for that frame rather than skip it."""
    shoulders_ok = _confident(keypoints, 5) and _confident(keypoints, 6)
    hips_ok = _confident(keypoints, 11) and _confident(keypoints, 12)

    if shoulders_ok and hips_ok:
        shoulder_mid = np.array([(keypoints[5][0] + keypoints[6][0]) / 2,
                                  (keypoints[5][1] + keypoints[6][1]) / 2])
        hip_mid      = np.array([(keypoints[11][0] + keypoints[12][0]) / 2,
                                  (keypoints[11][1] + keypoints[12][1]) / 2])
        torso_len = np.linalg.norm(shoulder_mid - hip_mid)
        # Foreshortened (near side-on) torso — the shoulder-hip distance
        # collapses even though both joints are confidently detected, not
        # because they're unreliable. TORSO_SCALE_MIN_RATIO is expressed
        # against the shoulder width itself so this isn't an absolute pixel
        # threshold (see plan Stage 1 step 4).
        shoulder_width = np.linalg.norm(
            np.array(keypoints[5][:2]) - np.array(keypoints[6][:2])
        )
        if torso_len >= TORSO_SCALE_MIN_RATIO * shoulder_width:
            return max(torso_len, 10.0)

    if shoulders_ok:
        shoulder_width = np.linalg.norm(
            np.array(keypoints[5][:2]) - np.array(keypoints[6][:2])
        )
        if shoulder_width > 0:
            return max(shoulder_width, 10.0)

    return None
