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

def determine_fight_state(detections, current_fight_state_frames, min_grappling_threshold, iou_grappling_threshold):
    red_fighter_bbox, blue_fighter_bbox = (None, None), (None, None)

    for detection in detections:
        if detection["class_id"] == LABEL_ID["fighter_red"]:
            red_fighter_bbox = detection["bbox_xyxy"]
        elif detection["class_id"] == LABEL_ID["fighter_blue"]:
            blue_fighter_bbox = detection["bbox_xyxy"]

    iou = compute_iou(red_fighter_bbox, blue_fighter_bbox)

    print(f"Fighters IoU: {iou}")

    if iou is not None and iou > iou_grappling_threshold:
        current_fight_state_frames += 1
    else:
        current_fight_state_frames = 0

    # In order to change the fight state, fighters need to be in that frame for a min_grappling_threshold number of frames
    if current_fight_state_frames >= min_grappling_threshold:
        current_fight_state = FightState.GRAPPLING
    else:
        current_fight_state = FightState.STRIKING
    return current_fight_state, current_fight_state_frames