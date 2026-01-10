import math
from models.constants import LABEL_ID
from models.fight_state import FightState

def calculate_rectangle_center(x1, y1, x2, y2):
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    return center_x, center_y

def calculate_distance_between_points(x1, y1, x2, y2):
    return math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

def calculate_fighter_centers(detections):
  red_center, blue_center = (None, None), (None, None)

  for detection in detections:
    if detection["class_id"] == LABEL_ID["fighter_red"]:
      red_center = calculate_rectangle_center(*detection["bbox_xyxy"])
    elif detection["class_id"] == LABEL_ID["fighter_blue"]:
      blue_center = calculate_rectangle_center(*detection["bbox_xyxy"])

  return red_center, blue_center

def determine_fight_state(current_distance, current_fight_state_frames, min_grappling_threshold, distance_threshold):
    if current_distance is not None and current_distance < distance_threshold:
        current_fight_state_frames += 1
    else:
        current_fight_state_frames = 0

    if current_fight_state_frames >= min_grappling_threshold:
        current_fight_state = FightState.GRAPPLING
    else:
        current_fight_state = FightState.STRIKING
    return current_fight_state, current_fight_state_frames