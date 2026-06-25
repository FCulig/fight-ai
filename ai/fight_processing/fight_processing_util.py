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
    HEAD_RADIUS_EAR_FACTOR,
    HEAD_RADIUS_SCALE_RATIO,
    HEAD_RADIUS_MIN_RATIO,
    HEAD_RADIUS_MAX_RATIO,
    HEAD_ABOVE_SHOULDER_RATIO,
    GRAPPLING_PUNCH_VELOCITY_RATIO,
    GRAPPLING_KICK_VELOCITY_RATIO,
    GRAPPLING_HEAD_CONTACT_RATIO,
    GRAPPLING_TORSO_CONTACT_RATIO,
    GRAPPLING_STRIKE_DIRECTION_MIN,
    KEYPOINT_MIN_CONFIDENCE,
    STRIKE_KEYPOINT_INDICES,
    STRIKING_CORE_KEYPOINT_INDICES,
    ONE_EURO_MIN_CUTOFF,
    ONE_EURO_BETA,
    ONE_EURO_D_CUTOFF,
    TORSO_VERTICAL_ANGLE_THRESHOLD,
    GROUND_VERTICAL_SPAN_RATIO,
    MIN_GRAPPLING_THRESHOLD,
    MIN_GROUND_THRESHOLD,
    DISTANCE_GRAPPLING_THRESHOLD,
    GRAPPLING_MIN_VISIBLE_KEYPOINTS,
)
from models.FightState import FightState, GRAPPLING_STATES
# Geometry helpers live in models.geometry to avoid a layering inversion
# (corner_assignment imports them too, and it runs before fight_processing).
from models.geometry import (
    get_fighter_scale,
    get_torso_rectangle,
    calculate_distance_between_fighters,
)


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
    Call per fighter; reset between fights by creating a new smoother.

    Joints below KEYPOINT_MIN_CONFIDENCE are passed through *without* updating the
    filter state — occluded/hallucinated coordinates must not corrupt the filter and
    bleed into later frames where the joint reappears.
    """
    filters = [[_OneEuroFilter(), _OneEuroFilter()] for _ in range(17)]

    def smooth(kp, frame_index):
        out = []
        for i, joint in enumerate(kp):
            conf = joint[2] if len(joint) > 2 else 1.0
            if conf >= KEYPOINT_MIN_CONFIDENCE:
                # Reliable joint — update filter and use smoothed value.
                sx = filters[i][0].filter(joint[0], frame_index)
                sy = filters[i][1].filter(joint[1], frame_index)
            else:
                # Unreliable joint — pass raw coordinates through; hold filter state
                # so the previous confident observation is not overwritten.
                sx, sy = joint[0], joint[1]
            out.append([sx, sy, conf])
        return out

    return smooth


def _fighter_keypoints_valid(kp):
    """Returns True when all strike-relevant joints have sufficient confidence."""
    if kp is None or len(kp) < 17:
        return False
    return all(kp[i][2] >= KEYPOINT_MIN_CONFIDENCE for i in STRIKE_KEYPOINT_INDICES)


def is_frame_valid(detections):
    """Thin bool wrapper: True only when both fighters pass the strict FULL bar.
    Kept for backward-compatibility with pose_verification.py which does not
    have a fight_state context.  Use frame_validity() inside process_fight."""
    red_kp = next((d["keypoints"] for d in detections if d.get("class_id") == 0), None)
    blue_kp = next((d["keypoints"] for d in detections if d.get("class_id") == 1), None)
    return _fighter_keypoints_valid(red_kp) and _fighter_keypoints_valid(blue_kp)


def _fighter_partial_valid(kp):
    """Returns True when a fighter has at least GRAPPLING_MIN_VISIBLE_KEYPOINTS
    confident strike-relevant joints (relaxed bar used in PARTIAL grappling frames)."""
    if kp is None or len(kp) < 17:
        return False
    confident = sum(1 for i in STRIKE_KEYPOINT_INDICES if kp[i][2] >= KEYPOINT_MIN_CONFIDENCE)
    return confident >= GRAPPLING_MIN_VISIBLE_KEYPOINTS


def _fighter_core_valid(kp):
    """Returns True when a fighter's core trunk joints (head + shoulders + hips,
    STRIKING_CORE_KEYPOINT_INDICES) are confident. This is enough to compute the
    torso centre, torso rectangle, head centre and body scale — everything the
    contact gate needs from a defender. The attacking arm is gated per-limb inside
    detect_strikes, so a blurred wrist no longer disqualifies the whole frame."""
    if kp is None or len(kp) < 17:
        return False
    return all(kp[i][2] >= KEYPOINT_MIN_CONFIDENCE for i in STRIKING_CORE_KEYPOINT_INDICES)


def frame_validity(detections, fight_state) -> str:
    """Graded frame validity.

    Returns:
        "FULL"    — both fighters pass the strict keypoint bar (all strike-relevant
                    joints confident).  Open-range striking runs as normal.
        "PARTIAL" — both fighters present with enough of the right joints to run
                    strike detection, but below the strict FULL bar:
                      * GRAPPLING states — at least GRAPPLING_MIN_VISIBLE_KEYPOINTS
                        confident joints (grappling strike detection).
                      * STRIKING — both fighters' core trunk joints confident
                        (open-range strike detection runs; the per-limb confidence
                        gate inside detect_strikes handles an occluded arm).
        "INVALID" — fewer than 2 fighter detections, or joint completeness falls
                    below even the relaxed bar.
    """
    red_kp  = next((d["keypoints"] for d in detections if d.get("class_id") == 0), None)
    blue_kp = next((d["keypoints"] for d in detections if d.get("class_id") == 1), None)

    if red_kp is None or blue_kp is None:
        return "INVALID"

    if _fighter_keypoints_valid(red_kp) and _fighter_keypoints_valid(blue_kp):
        return "FULL"

    if fight_state in GRAPPLING_STATES:
        if _fighter_partial_valid(red_kp) and _fighter_partial_valid(blue_kp):
            return "PARTIAL"
    else:
        if _fighter_core_valid(red_kp) and _fighter_core_valid(blue_kp):
            return "PARTIAL"

    return "INVALID"

# get_torso_rectangle, calculate_distance_between_fighters, and get_fighter_scale
# have been moved to models.geometry and are re-exported here for backward
# compatibility with any existing import sites.

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


def is_fighter_grounded(keypoints):
    """Returns True when a fighter's pose reads as on the canvas rather than
    standing. Two scale-invariant signals, OR'd so either one is sufficient:

      1. Torso tilt — angle of the shoulder-midpoint → hip-midpoint vector away
         from the vertical axis. ~0° standing, ~90° lying. Robust on a side-on
         broadcast view.
      2. Vertical compression — head→ankle y-extent divided by fighter scale.
         Collapses when the body is horizontal; backup for when the torso angle
         is ambiguous (e.g. a more overhead camera).
    """
    shoulder_mid = np.array([(keypoints[5][0] + keypoints[6][0]) / 2,
                             (keypoints[5][1] + keypoints[6][1]) / 2])
    hip_mid      = np.array([(keypoints[11][0] + keypoints[12][0]) / 2,
                             (keypoints[11][1] + keypoints[12][1]) / 2])

    torso_vec = hip_mid - shoulder_mid
    # Angle from the vertical axis (0,1): 0° upright, 90° horizontal.
    torso_angle = np.degrees(np.arctan2(abs(torso_vec[0]), abs(torso_vec[1]) + 1e-6))

    # Vertical span across head and ankles, normalised by body scale.
    ys = [keypoints[0][1], keypoints[15][1], keypoints[16][1]]
    vertical_span = max(ys) - min(ys)
    span_ratio = vertical_span / get_fighter_scale(keypoints)

    return (torso_angle > TORSO_VERTICAL_ANGLE_THRESHOLD or
            span_ratio < GROUND_VERTICAL_SPAN_RATIO)


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
    """Returns the head centre: average of the *confident* points among nose (0),
    left ear (3), right ear (4).

    Confidence-gated on purpose — in a side-on broadcast view the far ear is
    routinely occluded or hallucinated, and averaging that garbage coordinate
    drags the head centre toward the torso, corrupting head-vs-body
    classification right at the boundary. Falls back to the nose alone, then to a
    point one head-height above the shoulder midpoint when no head joint is
    confident."""
    head_idx = [0, 3, 4]
    pts = [keypoints[i][:2] for i in head_idx
           if len(keypoints[i]) > 2 and keypoints[i][2] >= KEYPOINT_MIN_CONFIDENCE]
    if pts:
        return np.array(pts).mean(axis=0)

    # No confident head joint — estimate from the shoulder line.
    shoulder_mid = np.array([(keypoints[5][0] + keypoints[6][0]) / 2,
                             (keypoints[5][1] + keypoints[6][1]) / 2])
    # Image y increases downward, so the head is above (smaller y) the shoulders.
    return shoulder_mid - np.array([0.0, HEAD_ABOVE_SHOULDER_RATIO * get_fighter_scale(keypoints)])


def get_head_radius(keypoints, scale):
    """Radius (px) of the head zone used for head-vs-body classification.

    Uses the ear-to-ear span when both ears are confident (the full head width
    tracks that span), otherwise a fraction of body scale. Clamped to a sane band
    of the scale so a degenerate pose can't make the head zone absurd."""
    l_ear, r_ear = keypoints[3], keypoints[4]
    if (len(l_ear) > 2 and len(r_ear) > 2 and
            l_ear[2] >= KEYPOINT_MIN_CONFIDENCE and r_ear[2] >= KEYPOINT_MIN_CONFIDENCE):
        ear_span = np.linalg.norm(np.array(l_ear[:2]) - np.array(r_ear[:2]))
        radius = ear_span * HEAD_RADIUS_EAR_FACTOR
    else:
        radius = HEAD_RADIUS_SCALE_RATIO * scale
    return float(np.clip(radius, HEAD_RADIUS_MIN_RATIO * scale, HEAD_RADIUS_MAX_RATIO * scale))


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


def detect_strikes(red_kp, blue_kp, prev_red_kp, prev_blue_kp, strike_state, fps, frame_idx=0, grappling=False, ground=False, diag=None):
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
        grappling:                  When True, use lower velocity ratios and replace the
                                    open-range contact-proximity gate with a directional
                                    gate (relaxed proximity + velocity aimed at a target
                                    zone) that rejects pummeling/gripping false positives.
                                    Strike types are prefixed "clinch_" (standing clinch)
                                    or "ground_" when `ground` is also True.
        ground:                     When True (and grappling), emit ground-and-pound
                                    labels ("ground_punch" / "ground_knee") instead of
                                    the standing-clinch labels. Ignored unless grappling.

    Returns:
        List of dicts: [{"fighter": "fighter_red"|"fighter_blue", "type": <event_type>}, ...]
    """
    strikes = []

    red_center  = np.array([(red_kp[5][0]  + red_kp[6][0])  / 2, (red_kp[5][1]  + red_kp[6][1])  / 2])
    blue_center = np.array([(blue_kp[5][0] + blue_kp[6][0]) / 2, (blue_kp[5][1] + blue_kp[6][1]) / 2])

    red_torso_rect  = get_torso_rectangle(red_kp)
    blue_torso_rect = get_torso_rectangle(blue_kp)
    red_head        = get_head_center(red_kp)
    blue_head       = get_head_center(blue_kp)

    red_scale  = get_fighter_scale(red_kp)
    blue_scale = get_fighter_scale(blue_kp)

    # Max age (frames) of a per-limb velocity baseline before it is considered
    # stale and reset — keeps velocity meaningful when a limb has been occluded
    # for a long stretch. ~0.3 s of motion.
    max_base_gap = max(1, round(fps * 0.3))

    checks = [
        # attacker label, attacker kp, attacker torso centre, attacker scale,
        # opp head, opp torso rect, opp kp, opp scale, limb state
        ("fighter_red",  red_kp,  red_center,  red_scale,
         blue_head, blue_torso_rect, blue_kp,  blue_scale, strike_state["red"]),
        ("fighter_blue", blue_kp, blue_center, blue_scale,
         red_head,  red_torso_rect,  red_kp,   red_scale,  strike_state["blue"]),
    ]

    for (fighter_label, kp, atk_center, atk_scale,
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

            cur_distal = np.array(kp[distal][:2])

            # Velocity baseline: the LAST frame in which this specific limb was
            # confident (not merely the previous processed frame). Because blurred
            # impact frames are skipped above, this baseline naturally spans the
            # blur so the displacement still captures the full strike — while never
            # using an occluded/hallucinated coordinate. Multiplied by fps (not
            # divided by the gap) to preserve the existing threshold tuning.
            base = state.get("vel_base")
            if base is None or (frame_idx - base["frame"]) > max_base_gap:
                # No usable baseline yet (first sight or stale) — seed it and wait.
                state["vel_base"] = {"distal": cur_distal, "center": atk_center,
                                     "frame": frame_idx}
                state["extension_frames"] = 0
                continue

            angle = compute_angle(kp[proximal], kp[mid], kp[distal])
            distal_disp = cur_distal - base["distal"]
            center_disp = atk_center - base["center"]
            relative_vel = distal_disp - center_disp        # remove locomotion
            # Convert px → px/sec, then normalise by attacker scale → scale/sec
            speed_per_sec = np.linalg.norm(relative_vel) * fps
            speed_normalised = speed_per_sec / atk_scale

            # Advance the baseline to this confident observation for next frame.
            state["vel_base"] = {"distal": cur_distal, "center": atk_center,
                                 "frame": frame_idx}

            # Accept straight strikes (jab/cross) OR bent-arm strikes (hook/uppercut).
            # Kicks only use the straight/extension path.
            if is_kick:
                angle_ok = angle > angle_thresh
            else:
                straight = angle > ARM_EXTENSION_THRESHOLD
                bent     = PUNCH_BENT_ANGLE_MIN <= angle <= PUNCH_BENT_ANGLE_MAX
                angle_ok = straight or bent

            # Diagnostic: record the speed of every standing arm extension (angle ok,
            # before the velocity threshold) so the velocity distribution of real
            # punch motions is visible — used to set PUNCH_VELOCITY_RATIO correctly.
            if diag is not None and not grappling and not is_kick and angle_ok:
                diag["extended"].append(float(speed_normalised))

            if angle_ok and speed_normalised > vel_ratio:
                state["extension_frames"] += 1
            else:
                state["extension_frames"] = 0
                continue

            if state["extension_frames"] < STRIKE_EXTENSION_FRAMES:
                continue

            # Contact check: distances normalised by defender scale.
            # In grappling mode the open-range proximity gate is replaced by a
            # directional gate (relaxed proximity + velocity aimed at a target zone).
            end = np.array(kp[distal][:2])
            strike_type = None

            if grappling:
                # Fighters are entangled, so raw proximity no longer discriminates a
                # strike from pummeling / gripping (the hands are near the torso either
                # way). The discriminating signal is DIRECTION: a real short strike
                # drives the end-effector toward a target zone, whereas swimming for
                # underhooks / framing / gripping moves it laterally or pulls it back.
                prefix = "ground" if ground else "clinch"

                head_dist_norm  = np.linalg.norm(end - opp_head) / def_scale
                torso_dist_norm = (distance_to_rect(end, opp_torso_rect) / def_scale
                                   if opp_torso_rect else float('inf'))
                near_target = (head_dist_norm < GRAPPLING_HEAD_CONTACT_RATIO or
                               torso_dist_norm < GRAPPLING_TORSO_CONTACT_RATIO)

                # Aim the alignment check at whichever zone is closer.
                if opp_torso_rect:
                    opp_torso_center = np.array([
                        (opp_torso_rect[0] + opp_torso_rect[2]) / 2,
                        (opp_torso_rect[1] + opp_torso_rect[3]) / 2,
                    ])
                else:
                    opp_torso_center = opp_head
                target = opp_head if head_dist_norm <= torso_dist_norm else opp_torso_center
                to_target = target - end
                to_target_mag = np.linalg.norm(to_target)
                vel_mag = np.linalg.norm(relative_vel)
                alignment = (float(np.dot(relative_vel, to_target) / (vel_mag * to_target_mag))
                             if vel_mag > 1e-6 and to_target_mag > 1e-6 else -1.0)

                if near_target and alignment > GRAPPLING_STRIKE_DIRECTION_MIN:
                    strike_type = f"{prefix}_knee" if is_kick else f"{prefix}_punch"
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
                    # Acceptance: did the punch land near the opponent at all?
                    # (unchanged reach — same two ratios as before).
                    landed = (head_dist_norm < HEAD_CONTACT_RATIO or
                              torso_dist_norm < TORSO_CONTACT_RATIO)
                    if landed:
                        # Head-vs-body by NEAREST REGION, not head-first priority.
                        # Each distance is "how far outside the region" (0 when the
                        # wrist is inside it): the head circle vs the torso rectangle.
                        # A borderline head shot just outside the head circle is no
                        # longer captured by the torso test merely because the head
                        # sits above the torso's top edge.
                        head_radius = get_head_radius(opp_kp, def_scale)
                        head_region_dist  = max(0.0, np.linalg.norm(end - opp_head) - head_radius)
                        torso_region_dist = (distance_to_rect(end, opp_torso_rect)
                                             if opp_torso_rect else float('inf'))
                        if head_region_dist <= torso_region_dist:
                            strike_type = f"{punch_label}_head"
                        else:
                            strike_type = f"{punch_label}_body"

                # Diagnostic: every standing PUNCH candidate that cleared the angle +
                # velocity + extension-frame gates is recorded with its normalised
                # contact distances and whether the contact gate accepted it. Lets us
                # confirm whether the contact gate is what suppresses standing punches.
                if diag is not None and not is_kick:
                    diag["candidates"].append({
                        "head":  float(head_dist_norm),
                        "torso": float(torso_dist_norm),
                        "speed": float(speed_normalised),
                        "hit":   strike_type is not None,
                    })

            if strike_type:
                strikes.append({
                    "fighter":  fighter_label,
                    "type":     strike_type,
                    "defender": "fighter_blue" if fighter_label == "fighter_red" else "fighter_red",
                })
                state["cooldown"] = STRIKE_COOLDOWN_FRAMES
                state["extension_frames"] = 0

    return strikes


def determine_fight_state(detections, counters, current_fight_state):
    """
    Classifies the current fight state into STRIKING, CLINCH, or GROUND.

    Two axes:
      * Proximity — torso-rectangle distance between fighters. At/above
        DISTANCE_GRAPPLING_THRESHOLD the candidate is STRIKING; below it the
        fighters are entangled (clinch or ground).
      * Posture — when entangled, GROUND if *either* fighter reads as grounded
        (knockdown, sprawl, scramble), otherwise CLINCH (standing grapple).

    Per-candidate consecutive-frame counters provide hysteresis: a candidate
    must hold for its minimum frame count before the state transitions. STRIKING
    and CLINCH use MIN_GRAPPLING_THRESHOLD; GROUND uses the slower
    MIN_GROUND_THRESHOLD.

    Args:
        detections:          List of detected fighters with keypoints.
        counters:            Dict {"striking": int, "clinch": int, "ground": int}
                             of consecutive-frame counts (mutated and returned).
        current_fight_state: The state carried over from the previous frame.

    Returns:
        tuple: (current_fight_state, counters)
    """
    red_fighter_keypoints, blue_fighter_keypoints = None, None

    for detection in detections:
        if detection["class_id"] == LABEL_ID["fighter_red"]:
            red_fighter_keypoints = detection["keypoints"]
        elif detection["class_id"] == LABEL_ID["fighter_blue"]:
            blue_fighter_keypoints = detection["keypoints"]

    candidate = None
    if red_fighter_keypoints is not None and blue_fighter_keypoints is not None:
        red_torso = get_torso_rectangle(red_fighter_keypoints)
        blue_torso = get_torso_rectangle(blue_fighter_keypoints)
        distance_between_fighters = calculate_distance_between_fighters(red_torso, blue_torso)

        if distance_between_fighters >= DISTANCE_GRAPPLING_THRESHOLD:
            candidate = "striking"
        elif (is_fighter_grounded(red_fighter_keypoints) or
              is_fighter_grounded(blue_fighter_keypoints)):
            candidate = "ground"
        else:
            candidate = "clinch"

    # Bump the active candidate, reset the others. If neither fighter is present
    # (candidate is None) leave all counters unchanged and hold the prior state.
    if candidate is not None:
        for key in counters:
            counters[key] = counters[key] + 1 if key == candidate else 0

    if counters["ground"] >= MIN_GROUND_THRESHOLD:
        current_fight_state = FightState.GROUND
    elif counters["clinch"] >= MIN_GRAPPLING_THRESHOLD:
        current_fight_state = FightState.CLINCH
    elif counters["striking"] >= MIN_GRAPPLING_THRESHOLD:
        current_fight_state = FightState.STRIKING

    return current_fight_state, counters