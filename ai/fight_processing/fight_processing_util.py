import numpy as np
from collections import deque
from models.constants import (
    LABEL_ID,
    MIN_HIP_DROP_RATIO,
    HEAD_ABOVE_SHOULDER_RATIO,
    KEYPOINT_MIN_CONFIDENCE,
    STRIKE_KEYPOINT_INDICES,
    STRIKING_CORE_KEYPOINT_INDICES,
    ONE_EURO_MIN_CUTOFF,
    ONE_EURO_BETA,
    ONE_EURO_D_CUTOFF,
    TORSO_VERTICAL_ANGLE_THRESHOLD,
    GROUND_VERTICAL_SPAN_RATIO,
    FIGHT_STATE_SMOOTHING_WINDOW_SECS,
    FIGHT_STATE_MIN_DWELL_SECS,
    DISTANCE_GRAPPLING_RATIO,
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
    have a fight_state context.  Use frame_usable() inside process_fight."""
    red_kp = next((d["keypoints"] for d in detections if d.get("class_id") == 0), None)
    blue_kp = next((d["keypoints"] for d in detections if d.get("class_id") == 1), None)
    return _fighter_keypoints_valid(red_kp) and _fighter_keypoints_valid(blue_kp)


def _fighter_partial_valid(kp):
    """At least GRAPPLING_MIN_VISIBLE_KEYPOINTS confident joints — the relaxed
    bar for tangled clinch/ground frames, where limbs occlude each other."""
    if kp is None or len(kp) < 17:
        return False
    confident = sum(1 for i in STRIKE_KEYPOINT_INDICES if kp[i][2] >= KEYPOINT_MIN_CONFIDENCE)
    return confident >= GRAPPLING_MIN_VISIBLE_KEYPOINTS


def _fighter_core_valid(kp):
    """Core trunk joints (head + shoulders + hips, STRIKING_CORE_KEYPOINT_INDICES)
    confident — enough for torso centre, torso rectangle, head centre and scale,
    which is everything determine_fight_state and the recoil check read."""
    if kp is None or len(kp) < 17:
        return False
    return all(kp[i][2] >= KEYPOINT_MIN_CONFIDENCE for i in STRIKING_CORE_KEYPOINT_INDICES)


def frame_usable(detections, fight_state) -> bool:
    """Whether a frame carries enough pose to advance the fight-state machine:
    both fighters present, and either their core trunk joints confident
    (STRIKING) or at least GRAPPLING_MIN_VISIBLE_KEYPOINTS joints each
    (CLINCH/GROUND, where fighters occlude each other). Demanding every joint
    instead would drop ~95% of standing frames — broadcast cameras occlude
    legs constantly."""
    red_kp  = next((d["keypoints"] for d in detections if d.get("class_id") == 0), None)
    blue_kp = next((d["keypoints"] for d in detections if d.get("class_id") == 1), None)
    if red_kp is None or blue_kp is None:
        return False
    if _fighter_keypoints_valid(red_kp) and _fighter_keypoints_valid(blue_kp):
        return True
    check = _fighter_partial_valid if fight_state in GRAPPLING_STATES else _fighter_core_valid
    return check(red_kp) and check(blue_kp)

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
    standing. Two signals; the second is only used when it's actually usable:

      1. Torso tilt — angle of the shoulder-midpoint → hip-midpoint vector away
         from the vertical axis. ~0° standing, ~90° lying. Robust on a side-on
         broadcast view. Scale-invariant (an angle, not a distance) so no
         confidence gate is needed beyond what shoulders/hips already get
         elsewhere in the pipeline.
      2. Vertical compression — head→ankle y-extent divided by fighter scale.
         Backup for when the torso angle is ambiguous (e.g. a more overhead
         camera) — but ankles are routinely occluded in a standing clinch, and
         a hallucinated ankle lands near the hips, collapsing this ratio and
         misreading GROUNDED while standing. Dropped entirely (not
         defaulted to False by a fake coordinate) unless nose + both ankles
         are confident and a scale is available.
    """
    shoulder_mid = np.array([(keypoints[5][0] + keypoints[6][0]) / 2,
                             (keypoints[5][1] + keypoints[6][1]) / 2])
    hip_mid      = np.array([(keypoints[11][0] + keypoints[12][0]) / 2,
                             (keypoints[11][1] + keypoints[12][1]) / 2])

    torso_vec = hip_mid - shoulder_mid
    # Angle from the vertical axis (0,1): 0° upright, 90° horizontal.
    torso_angle = np.degrees(np.arctan2(abs(torso_vec[0]), abs(torso_vec[1]) + 1e-6))
    if torso_angle > TORSO_VERTICAL_ANGLE_THRESHOLD:
        return True

    scale = get_fighter_scale(keypoints)
    ankles_confident = all(
        len(keypoints[i]) > 2 and keypoints[i][2] >= KEYPOINT_MIN_CONFIDENCE
        for i in (0, 15, 16)
    )
    if scale is None or not ankles_confident:
        return False

    ys = [keypoints[0][1], keypoints[15][1], keypoints[16][1]]
    vertical_span = max(ys) - min(ys)
    span_ratio = vertical_span / scale
    return span_ratio < GROUND_VERTICAL_SPAN_RATIO


def determine_takedown_initiator(hip_history):
    """
    Determines which fighter initiated a takedown by comparing hip height change
    over the buffered frames leading up to grappling state entry.

    Args:
        hip_history: deque of dicts with keys 'red'/'blue' (hip y-coordinate)
                     and 'red_scale'/'blue_scale' (get_fighter_scale at that
                     frame, possibly None). Most recent frame is last.

    Returns:
        'fighter_red', 'fighter_blue', or None if inconclusive.
    """
    if len(hip_history) < 2:
        return None

    oldest = hip_history[0]
    newest = hip_history[-1]

    red_drop = newest["red"] - oldest["red"]   # positive = hips moved down (being taken down)
    blue_drop = newest["blue"] - oldest["blue"]

    # MIN_HIP_DROP_RATIO is a fraction of fighter scale, not an absolute pixel
    # count — average whatever confident scale readings are available at the
    # two endpoints; fall back to 1.0 (degrading to the old absolute-pixel
    # behaviour) only if none are usable, which is rare enough not to be
    # worth discarding the whole comparison over.
    scales = [s for s in (oldest.get("red_scale"), oldest.get("blue_scale"),
                          newest.get("red_scale"), newest.get("blue_scale")) if s]
    scale = sum(scales) / len(scales) if scales else 1.0
    min_hip_drop = MIN_HIP_DROP_RATIO * scale

    # The fighter with the larger hip drop is the one being taken down — the other initiated
    if red_drop - blue_drop > min_hip_drop:
        return "fighter_blue"  # red was taken down, blue initiated
    elif blue_drop - red_drop > min_hip_drop:
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

    # No confident head joint — estimate from the shoulder line. This is
    # already a last-resort fallback operating on whatever shoulder
    # coordinates exist regardless of their own confidence, so a missing
    # scale (shoulders too unconfident to trust) falls back to the same 10px
    # floor get_fighter_scale itself uses, rather than crashing.
    shoulder_mid = np.array([(keypoints[5][0] + keypoints[6][0]) / 2,
                             (keypoints[5][1] + keypoints[6][1]) / 2])
    scale = get_fighter_scale(keypoints) or 10.0
    # Image y increases downward, so the head is above (smaller y) the shoulders.
    return shoulder_mid - np.array([0.0, HEAD_ABOVE_SHOULDER_RATIO * scale])


def determine_fight_state(detections, state, current_fight_state, fps):
    """
    Classifies the current fight state into STRIKING, CLINCH, or GROUND.

    Two axes:
      * Proximity — torso-rectangle distance between fighters, normalised by
        fighter scale. At/above DISTANCE_GRAPPLING_RATIO the candidate is
        STRIKING; below it the fighters are entangled (clinch or ground).
        When the distance or either fighter's scale is unusable this frame
        (unconfident keypoints), no candidate is read at all — an unknown
        distance must not silently read as "far apart, therefore STRIKING".
      * Posture — when entangled, GROUND if *either* fighter reads as grounded
        (knockdown, sprawl, scramble), otherwise CLINCH (standing grapple).

    Temporal smoothing (two stages, replacing the old 3-/5-consecutive-frame
    counters — 0.06-0.1s at 50fps was no real hysteresis at all):
      1. A majority vote over a FIGHT_STATE_SMOOTHING_WINDOW_SECS rolling
         window of raw per-frame candidates — the categorical equivalent of a
         median filter (there's no numeric ordering to smooth a median over
         across three state names).
      2. The smoothed candidate only becomes the live state once it differs
         from the current state AND at least FIGHT_STATE_MIN_DWELL_SECS has
         passed since the last transition.

    Args:
        detections:          List of detected fighters with keypoints.
        state:                Dict {"window": deque, "since_transition": int},
                             mutated and returned. Callers should initialise
                             with {} — the deque is (re)built on first use so
                             it always matches the current fps.
        current_fight_state: The state carried over from the previous frame.
        fps:                 Video frame rate, for converting the smoothing/
                             dwell windows from seconds to frames.

    Returns:
        tuple: (current_fight_state, state)
    """
    window_frames = max(1, round(fps * FIGHT_STATE_SMOOTHING_WINDOW_SECS))
    min_dwell_frames = max(1, round(fps * FIGHT_STATE_MIN_DWELL_SECS))

    if state.get("window") is None or state["window"].maxlen != window_frames:
        state["window"] = deque(maxlen=window_frames)
        # Allow a transition immediately once the window has real signal,
        # rather than forcing a full dwell wait from a cold start.
        state["since_transition"] = min_dwell_frames

    red_fighter_keypoints, blue_fighter_keypoints = None, None
    for detection in detections:
        if detection["class_id"] == LABEL_ID["fighter_red"]:
            red_fighter_keypoints = detection["keypoints"]
        elif detection["class_id"] == LABEL_ID["fighter_blue"]:
            blue_fighter_keypoints = detection["keypoints"]

    candidate = None
    if red_fighter_keypoints is not None and blue_fighter_keypoints is not None:
        red_torso  = get_torso_rectangle(red_fighter_keypoints)
        blue_torso = get_torso_rectangle(blue_fighter_keypoints)
        red_scale  = get_fighter_scale(red_fighter_keypoints)
        blue_scale = get_fighter_scale(blue_fighter_keypoints)
        distance   = calculate_distance_between_fighters(red_torso, blue_torso)

        if distance is not None and red_scale is not None and blue_scale is not None:
            avg_scale = (red_scale + blue_scale) / 2
            if distance >= DISTANCE_GRAPPLING_RATIO * avg_scale:
                candidate = "striking"
            elif (is_fighter_grounded(red_fighter_keypoints) or
                  is_fighter_grounded(blue_fighter_keypoints)):
                candidate = "ground"
            else:
                candidate = "clinch"
        # else: unusable this frame — candidate stays None, contributing no
        # vote rather than a garbage one.

    if candidate is not None:
        state["window"].append(candidate)
    state["since_transition"] += 1

    if state["window"]:
        counts: dict[str, int] = {}
        for c in state["window"]:
            counts[c] = counts.get(c, 0) + 1
        smoothed = max(counts, key=counts.get)
        target_state = {
            "striking": FightState.STRIKING,
            "clinch":   FightState.CLINCH,
            "ground":   FightState.GROUND,
        }[smoothed]

        if target_state != current_fight_state and state["since_transition"] >= min_dwell_frames:
            current_fight_state = target_state
            state["since_transition"] = 0

    return current_fight_state, state