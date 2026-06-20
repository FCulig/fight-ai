"""
Shared pure-geometry helpers used by both the corner-assignment stage
(video_processing) and the fight-processing stage.

Kept here to avoid a layering inversion: corner_assignment runs *before*
fight_processing in the pipeline, so it cannot import from fight_processing.
"""

import numpy as np


def get_torso_rectangle(keypoints):
    """Returns (x1, y1, x2, y2) torso rectangle from shoulders and hips
    (COCO keypoints 5, 6, 11, 12)."""
    indices = [5, 6, 11, 12]
    valid_points = [keypoints[i] for i in indices]

    if len(valid_points) < 2:
        return None

    points = np.array(valid_points)
    x1 = points[:, 0].min()
    y1 = points[:, 1].min()
    x2 = points[:, 0].max()
    y2 = points[:, 1].max()

    return (x1, y1, x2, y2)


def calculate_distance_between_fighters(rect1, rect2):
    """Distance between two torso rectangles (0 when they overlap)."""
    if not rect1 or not rect2:
        return float('inf')

    x1_min, y1_min, x1_max, y1_max = rect1
    x2_min, y2_min, x2_max, y2_max = rect2

    dx = max(0, max(x1_min, x2_min) - min(x1_max, x2_max))
    dy = max(0, max(y1_min, y2_min) - min(y1_max, y2_max))

    return np.sqrt(dx**2 + dy**2)


def get_fighter_scale(keypoints):
    """Body-size reference in pixels: distance from shoulder midpoint to hip
    midpoint.  Falls back to shoulder width when hips are foreshortened.
    Clamped to 10 px minimum to avoid division issues."""
    shoulder_mid = np.array([(keypoints[5][0] + keypoints[6][0]) / 2,
                              (keypoints[5][1] + keypoints[6][1]) / 2])
    hip_mid      = np.array([(keypoints[11][0] + keypoints[12][0]) / 2,
                              (keypoints[11][1] + keypoints[12][1]) / 2])
    torso_len = np.linalg.norm(shoulder_mid - hip_mid)
    if torso_len < 20:
        torso_len = np.linalg.norm(
            np.array(keypoints[5][:2]) - np.array(keypoints[6][:2])
        )
    return max(torso_len, 10.0)
