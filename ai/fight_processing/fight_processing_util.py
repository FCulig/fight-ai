import numpy as np
from collections import deque
from models.constants import LABEL_ID, MIN_HIP_DROP_THRESHOLD
from models.FightState import FightState

def is_frame_valid(detections):
    has_red_fighter = any(d.get('class_id') == 0 for d in detections)
    has_blue_fighter = any(d.get('class_id') == 1 for d in detections)
    has_all_keypoints = all(d["keypoints"] is not None and len(d["keypoints"]) >= 17 for d in detections)

    #print(f"Frame validation: has_red_fighter={has_red_fighter}, has_blue_fighter={has_blue_fighter}, has_all_keypoints={has_all_keypoints}")

    return has_red_fighter and has_blue_fighter and has_all_keypoints

def get_torso_rectangle(keypoints):
    """Returns (x1, y1, x2, y2) torso rectangle from shoulders and hips"""
    indices = [5, 6, 11, 12]  # left shoulder, right shoulder, left hip, right hip
    
    valid_points = [keypoints[i] for i in indices]
    
    if len(valid_points) < 2:  # need at least 2 points to form a rectangle
        return None
    
    points = np.array(valid_points)
    x1 = points[:, 0].min()
    y1 = points[:, 1].min()
    x2 = points[:, 0].max()
    y2 = points[:, 1].max()
    
    return (x1, y1, x2, y2)

def calculate_distance_between_fighters(rect1, rect2):
    if not rect1 or not rect2:
        print("One or both fighters are missing bounding boxes, cannot calculate distance.")
        return float('inf')
    
    x1_min, y1_min, x1_max, y1_max = rect1
    x2_min, y2_min, x2_max, y2_max = rect2
    
    # distance in x and y axes separately
    dx = max(0, max(x1_min, x2_min) - min(x1_max, x2_max))
    dy = max(0, max(y1_min, y2_min) - min(y1_max, y2_max))
    
    return np.sqrt(dx**2 + dy**2)  # 0 if rectangles overlap

def compute_iou(box_a, box_b):
    """
    box_a, box_b: YOLO bbox in xyxy format
    [x_min, y_min, x_max, y_max]
    """

    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    # intersection box
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter_area = iw * ih

    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)

    union_area = area_a + area_b - inter_area

    if union_area == 0:
        return 0.0

    return inter_area / union_area

def get_hip_height(keypoints):
    """Returns average y-coordinate of left and right hips (kp 11, 12). Higher value = lower on screen."""
    left_hip = keypoints[11]
    right_hip = keypoints[12]
    return (left_hip[1] + right_hip[1]) / 2.0


def determine_takedown_initiator(hip_history):
    """
    Determines which fighter initiated a takedown by comparing hip height change
    over the buffered frames leading up to grappling state entry.

    Args:
        hip_history: deque of dicts with keys 'red' and 'blue', each a hip y-coordinate.
                     Most recent frame is last.

    Returns:
        'fighter_red', 'fighter_blue', or None if inconclusive.
    """
    if len(hip_history) < 2:
        return None

    oldest = hip_history[0]
    newest = hip_history[-1]

    red_drop = newest["red"] - oldest["red"]   # positive = hips moved down (being taken down)
    blue_drop = newest["blue"] - oldest["blue"]

    # The fighter with the larger hip drop is the one being taken down — the other initiated
    if red_drop - blue_drop > MIN_HIP_DROP_THRESHOLD:
        return "fighter_blue"  # red was taken down, blue initiated
    elif blue_drop - red_drop > MIN_HIP_DROP_THRESHOLD:
        return "fighter_red"   # blue was taken down, red initiated

    return None  # inconclusive — could be a clinch or both dropped


def determine_fight_state(detections, grappling_frames, striking_frames, current_fight_state, min_frames_threshold, distance_grappling_threshold):
    """
    Determines the current fight state (GRAPPLING or STRIKING) based on the Intersection over Union (IoU) 
    of the fighter bounding boxes. When fighters' bounding boxes overlap significantly, it indicates a grappling 
    state. The function tracks consecutive frames where the IoU exceeds the threshold and transitions to GRAPPLING 
    state only after a minimum number of consecutive frames (min_grappling_threshold) are met. Otherwise, 
    the default state is STRIKING.
    
    Args:
        detections: List of detected fighters with bounding boxes
        current_fight_state_frames: Counter for consecutive frames in current fight state
        min_grappling_threshold: Minimum consecutive frames required to transition to GRAPPLING state
        iou_grappling_threshold: IoU threshold above which fighters are considered to be grappling
    
    Returns:
        tuple: (current_fight_state, current_fight_state_frames) - The determined fight state and frame counter
    """
    red_fighter_keypoints, blue_fighter_keypoints = None, None

    for detection in detections:
        if detection["class_id"] == LABEL_ID["fighter_red"]:
            red_fighter_keypoints = detection["keypoints"]
        elif detection["class_id"] == LABEL_ID["fighter_blue"]:
            blue_fighter_keypoints = detection["keypoints"]

    distance_between_fighters = None
    if red_fighter_keypoints is not None and blue_fighter_keypoints is not None:
        red_torso = get_torso_rectangle(red_fighter_keypoints)
        blue_torso = get_torso_rectangle(blue_fighter_keypoints)
        distance_between_fighters = calculate_distance_between_fighters(red_torso, blue_torso)

    if distance_between_fighters is not None:
        if distance_between_fighters < distance_grappling_threshold:
            grappling_frames += 1
            striking_frames = 0
        else:
            striking_frames += 1
            grappling_frames = 0
    # if None, leave both counters unchanged

    if grappling_frames >= min_frames_threshold:
        current_fight_state = FightState.GRAPPLING
    elif striking_frames >= min_frames_threshold:
        current_fight_state = FightState.STRIKING

    return current_fight_state, grappling_frames, striking_frames