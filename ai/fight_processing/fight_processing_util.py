import numpy as np
from collections import deque
from models.constants import (
    LABEL_ID,
    MIN_HIP_DROP_THRESHOLD,
    PUNCH_VELOCITY_RATIO,
    KICK_VELOCITY_RATIO,
    ARM_EXTENSION_THRESHOLD,
    PUNCH_BENT_ANGLE_MIN,
    PUNCH_BENT_ANGLE_MAX,
    LEG_EXTENSION_THRESHOLD,
    STRIKE_COOLDOWN_FRAMES,
    STRIKE_EXTENSION_FRAMES,
    HEAD_CONTACT_RATIO,
    TORSO_CONTACT_RATIO,
    LEG_CONTACT_RATIO,
    GRAPPLING_PUNCH_VELOCITY_RATIO,
    GRAPPLING_KICK_VELOCITY_RATIO,
    KEYPOINT_MIN_CONFIDENCE,
    STRIKE_KEYPOINT_INDICES,
    ONE_EURO_MIN_CUTOFF,
    ONE_EURO_BETA,
    ONE_EURO_D_CUTOFF,
)
from models.FightState import FightState


class _OneEuroFilter:
    """Per-scalar One-Euro filter. Call filter(x, t) at each frame."""
    def __init__(self):
        self._x_prev = None
        self._dx_prev = 0.0
        self._t_prev = None

    def _alpha(self, cutoff, dt):
        tau = 1.0 / (2 * np.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filter(self, x, t):
        if self._t_prev is None:
            self._x_prev = x
            self._t_prev = t
            return x
        dt = max(t - self._t_prev, 1e-6)
        # Derivative estimate
        dx = (x - self._x_prev) / dt
        a_d = self._alpha(ONE_EURO_D_CUTOFF, dt)
        dx_hat = a_d * dx + (1 - a_d) * self._dx_prev
        # Adaptive cutoff
        cutoff = ONE_EURO_MIN_CUTOFF + ONE_EURO_BETA * abs(dx_hat)
        a = self._alpha(cutoff, dt)
        x_hat = a * x + (1 - a) * self._x_prev
        self._x_prev = x_hat
        self._dx_prev = dx_hat
        self._t_prev = t
        return x_hat


def make_keypoint_smoother():
    """Returns a function smooth(kp, frame_index) → smoothed kp list.
    Maintains one One-Euro filter per joint per axis (17 joints × 2 axes = 34 filters).
    Call per fighter; reset between fights by creating a new smoother."""
    filters = [[_OneEuroFilter(), _OneEuroFilter()] for _ in range(17)]

    def smooth(kp, frame_index):
        out = []
        for i, joint in enumerate(kp):
            sx = filters[i][0].filter(joint[0], frame_index)
            sy = filters[i][1].filter(joint[1], frame_index)
            # Preserve original confidence value
            conf = joint[2] if len(joint) > 2 else 1.0
            out.append([sx, sy, conf])
        return out

    return smooth


def _fighter_keypoints_valid(kp):
    """Returns True when all strike-relevant joints have sufficient confidence."""
    if kp is None or len(kp) < 17:
        return False
    return all(kp[i][2] >= KEYPOINT_MIN_CONFIDENCE for i in STRIKE_KEYPOINT_INDICES)


def is_frame_valid(detections):
    """Frame is valid when both fighters are present and their strike-relevant joints
    are all above KEYPOINT_MIN_CONFIDENCE. Relaxed from requiring all 17 keypoints
    to avoid discarding frames with only minor occlusion."""
    red_kp = next((d["keypoints"] for d in detections if d.get("class_id") == 0), None)
    blue_kp = next((d["keypoints"] for d in detections if d.get("class_id") == 1), None)
    return _fighter_keypoints_valid(red_kp) and _fighter_keypoints_valid(blue_kp)

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

def get_fighter_scale(keypoints):
    """Body-size reference in pixels: distance from shoulder midpoint to hip midpoint.
    Used to normalize velocity and contact thresholds so they are invariant to camera
    zoom and fighter distance from the camera. Falls back to shoulder width when hips
    are unreliable (foreshortening). Clamped to 10px minimum to avoid division issues."""
    shoulder_mid = np.array([(keypoints[5][0] + keypoints[6][0]) / 2,
                              (keypoints[5][1] + keypoints[6][1]) / 2])
    hip_mid      = np.array([(keypoints[11][0] + keypoints[12][0]) / 2,
                              (keypoints[11][1] + keypoints[12][1]) / 2])
    torso_len = np.linalg.norm(shoulder_mid - hip_mid)
    if torso_len < 20:
        # Fallback: shoulder width
        torso_len = np.linalg.norm(
            np.array(keypoints[5][:2]) - np.array(keypoints[6][:2])
        )
    return max(torso_len, 10.0)


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


def get_head_center(keypoints):
    """Returns the average position of nose (0), left ear (3), right ear (4)."""
    pts = np.array([keypoints[0][:2], keypoints[3][:2], keypoints[4][:2]])
    return pts.mean(axis=0)


def get_lead_hand_side(kp, opp_kp):
    """Returns 'left' or 'right' (COCO joint labelling) for the attacker's lead hand.
    Lead hand = same side as the lead foot (the foot horizontally closer to the opponent)."""
    opp_x = (opp_kp[5][0] + opp_kp[6][0]) / 2  # opponent shoulder center x
    left_ankle_x  = kp[15][0]
    right_ankle_x = kp[16][0]
    left_dist  = abs(left_ankle_x  - opp_x)
    right_dist = abs(right_ankle_x - opp_x)
    return "left" if left_dist < right_dist else "right"


def classify_punch_type(limb_key, angle, wrist_rel_vel, kp, opp_kp):
    """Returns a punch-type prefix string: jab | cross | hook | uppercut.
    straight path (angle > ARM_EXTENSION_THRESHOLD) → jab (lead) or cross (rear).
    bent path → uppercut if wrist moves mostly upward, hook otherwise."""
    is_straight = angle >= ARM_EXTENSION_THRESHOLD
    hand_side = "left" if "left" in limb_key else "right"
    lead_side = get_lead_hand_side(kp, opp_kp)

    if is_straight:
        return "jab" if hand_side == lead_side else "cross"
    else:
        # Bent-arm: direction of wrist relative velocity determines sub-type.
        # Image y increases downward, so negative dy = moving upward.
        vx, vy = wrist_rel_vel[0], wrist_rel_vel[1]
        return "uppercut" if (vy < 0 and abs(vy) >= abs(vx)) else "hook"


def point_to_segment_distance(p, a, b):
    """Returns the shortest distance from point p to the line segment a-b."""
    p, a, b = np.array(p[:2]), np.array(a[:2]), np.array(b[:2])
    ab = b - a
    t = np.clip(np.dot(p - a, ab) / (np.dot(ab, ab) + 1e-6), 0.0, 1.0)
    return np.linalg.norm(p - (a + t * ab))


def distance_to_rect(p, rect):
    """Returns distance from point p to the rectangle. Returns 0 if p is inside."""
    x, y = p[0], p[1]
    x1, y1, x2, y2 = rect
    dx = max(x1 - x, 0, x - x2)
    dy = max(y1 - y, 0, y - y2)
    return np.sqrt(dx**2 + dy**2)


def compute_angle(a, b, c):
    """Returns the angle in degrees at point b, formed by the a-b-c triplet."""
    a, b, c = np.array(a[:2]), np.array(b[:2]), np.array(c[:2])
    ba = a - b
    bc = c - b
    cos_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return np.degrees(np.arccos(np.clip(cos_angle, -1.0, 1.0)))


def detect_strikes(red_kp, blue_kp, prev_red_kp, prev_blue_kp, strike_state, fps, grappling=False):
    """
    Detects landed strikes by combining three filters:
      1. Limb extension angle above threshold (strike is being thrown)
      2. Torso-relative limb velocity above threshold (removes locomotion)
      3. End-effector proximity to an opponent body zone (confirms contact)

    Contact zones checked per limb type (in priority order):
      Wrist  → head (punch_head), torso (punch_body)
      Ankle  → head (head_kick),  torso (middle_kick), thigh segment (low_kick)

    strike_state is updated in place. Structure:
        {
            "red":  { "left_punch": {"cooldown": 0, "extension_frames": 0}, ... },
            "blue": { ... }
        }

    Args:
        red_kp / blue_kp:           Current frame keypoints (17-pt COCO, [x, y, conf])
        prev_red_kp / prev_blue_kp: Previous frame keypoints
        strike_state:               Per-fighter, per-limb state dict (mutated in place)
        fps:                        Video frame rate — used to convert velocity to px/sec.
        grappling:                  When True, use lower velocity ratios and skip the
                                    contact-proximity gate (fighters are already touching).
                                    Strike types are prefixed with "clinch_".

    Returns:
        List of dicts: [{"fighter": "fighter_red"|"fighter_blue", "type": <event_type>}, ...]
    """
    strikes = []

    red_center       = np.array([(red_kp[5][0]       + red_kp[6][0])       / 2, (red_kp[5][1]       + red_kp[6][1])       / 2])
    blue_center      = np.array([(blue_kp[5][0]      + blue_kp[6][0])      / 2, (blue_kp[5][1]      + blue_kp[6][1])      / 2])
    prev_red_center  = np.array([(prev_red_kp[5][0]  + prev_red_kp[6][0])  / 2, (prev_red_kp[5][1]  + prev_red_kp[6][1])  / 2])
    prev_blue_center = np.array([(prev_blue_kp[5][0] + prev_blue_kp[6][0]) / 2, (prev_blue_kp[5][1] + prev_blue_kp[6][1]) / 2])

    red_torso_vel  = red_center  - prev_red_center
    blue_torso_vel = blue_center - prev_blue_center

    red_torso_rect  = get_torso_rectangle(red_kp)
    blue_torso_rect = get_torso_rectangle(blue_kp)
    red_head        = get_head_center(red_kp)
    blue_head       = get_head_center(blue_kp)

    red_scale  = get_fighter_scale(red_kp)
    blue_scale = get_fighter_scale(blue_kp)

    checks = [
        # attacker label, attacker kp, prev kp, torso vel, attacker scale,
        # opp head, opp torso rect, opp kp, opp scale, limb state
        ("fighter_red",  red_kp,  prev_red_kp,  red_torso_vel,  red_scale,
         blue_head, blue_torso_rect, blue_kp,  blue_scale, strike_state["red"]),
        ("fighter_blue", blue_kp, prev_blue_kp, blue_torso_vel, blue_scale,
         red_head,  red_torso_rect,  red_kp,   red_scale,  strike_state["blue"]),
    ]

    for (fighter_label, kp, prev_kp, torso_vel, atk_scale,
         opp_head, opp_torso_rect, opp_kp, def_scale, limb_state) in checks:

        punch_vel = GRAPPLING_PUNCH_VELOCITY_RATIO if grappling else PUNCH_VELOCITY_RATIO
        kick_vel  = GRAPPLING_KICK_VELOCITY_RATIO  if grappling else KICK_VELOCITY_RATIO

        # (proximal, mid, distal, limb_key, vel_ratio, angle_thresh, is_kick)
        limb_checks = [
            (5,  7,  9,  "left_punch",  punch_vel, ARM_EXTENSION_THRESHOLD, False),
            (6,  8,  10, "right_punch", punch_vel, ARM_EXTENSION_THRESHOLD, False),
            (11, 13, 15, "left_kick",   kick_vel,  LEG_EXTENSION_THRESHOLD,  True),
            (12, 14, 16, "right_kick",  kick_vel,  LEG_EXTENSION_THRESHOLD,  True),
        ]

        for proximal, mid, distal, limb_key, vel_ratio, angle_thresh, is_kick in limb_checks:
            state = limb_state[limb_key]

            if state["cooldown"] > 0:
                state["cooldown"] -= 1
                state["extension_frames"] = 0
                continue

            # Skip limb when any joint is unreliable — avoids velocity spikes from
            # occluded / hallucinated keypoint coordinates.
            if any(kp[j][2] < KEYPOINT_MIN_CONFIDENCE for j in (proximal, mid, distal)):
                state["extension_frames"] = 0
                continue

            # Pre-filter: extension angle + torso-relative velocity
            angle = compute_angle(kp[proximal], kp[mid], kp[distal])
            abs_vel = np.array(kp[distal][:2]) - np.array(prev_kp[distal][:2])
            relative_vel = abs_vel - torso_vel
            # Convert px/frame → px/sec, then normalise by attacker scale → scale/sec
            speed_per_sec = np.linalg.norm(relative_vel) * fps
            speed_normalised = speed_per_sec / atk_scale

            # Accept straight strikes (jab/cross) OR bent-arm strikes (hook/uppercut).
            # Kicks only use the straight/extension path.
            if is_kick:
                angle_ok = angle > angle_thresh
            else:
                straight = angle > ARM_EXTENSION_THRESHOLD
                bent     = PUNCH_BENT_ANGLE_MIN <= angle <= PUNCH_BENT_ANGLE_MAX
                angle_ok = straight or bent

            if angle_ok and speed_normalised > vel_ratio:
                state["extension_frames"] += 1
            else:
                state["extension_frames"] = 0
                continue

            if state["extension_frames"] < STRIKE_EXTENSION_FRAMES:
                continue

            # Contact check: distances normalised by defender scale.
            # In grappling mode fighters are already touching — skip proximity and
            # classify by limb type only, prefixing the event with "clinch_".
            end = np.array(kp[distal][:2])
            strike_type = None

            if grappling:
                strike_type = "clinch_knee" if is_kick else "clinch_punch"
            else:
                head_dist_norm  = np.linalg.norm(end - opp_head) / def_scale
                torso_dist_norm = (distance_to_rect(end, opp_torso_rect) / def_scale
                                   if opp_torso_rect else float('inf'))

                if is_kick:
                    left_thigh_dist  = point_to_segment_distance(end, opp_kp[11], opp_kp[13])
                    right_thigh_dist = point_to_segment_distance(end, opp_kp[12], opp_kp[14])
                    thigh_dist_norm  = min(left_thigh_dist, right_thigh_dist) / def_scale

                    if head_dist_norm < HEAD_CONTACT_RATIO:
                        strike_type = "head_kick"
                    elif torso_dist_norm < TORSO_CONTACT_RATIO:
                        strike_type = "middle_kick"
                    elif thigh_dist_norm < LEG_CONTACT_RATIO:
                        strike_type = "low_kick"
                else:
                    punch_label = classify_punch_type(limb_key, angle, relative_vel, kp, opp_kp)
                    if head_dist_norm < HEAD_CONTACT_RATIO:
                        strike_type = f"{punch_label}_head"
                    elif torso_dist_norm < TORSO_CONTACT_RATIO:
                        strike_type = f"{punch_label}_body"

            if strike_type:
                strikes.append({
                    "fighter":  fighter_label,
                    "type":     strike_type,
                    "defender": "fighter_blue" if fighter_label == "fighter_red" else "fighter_red",
                })
                state["cooldown"] = STRIKE_COOLDOWN_FRAMES
                state["extension_frames"] = 0

    return strikes


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