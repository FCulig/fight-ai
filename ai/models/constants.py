LABEL_ID = {
    "fighter_red": 0,
    "fighter_blue": 1,
    "referee": 2
}

# Mininum number of frames for which delta distance needs to hold value in order for grappling to start
MIN_GRAPPLING_THRESHOLD = 3

# Distance threshold to determine if fighters are grappling (clinch or ground)
DISTANCE_GRAPPLING_THRESHOLD = 20

# --- Posture: standing (clinch) vs grounded (ground game) ---
# Within grapple distance, posture splits CLINCH from GROUND.
# Torso vector = shoulder-midpoint → hip-midpoint. Tilt from the vertical axis
# (degrees): ~0° standing upright, ~90° lying horizontal. Above this a fighter
# reads as grounded.
TORSO_VERTICAL_ANGLE_THRESHOLD = 50
# Vertical body span (head→ankle y-extent) divided by fighter scale. Collapses
# when a fighter is on the canvas. Below this the body reads as grounded.
GROUND_VERTICAL_SPAN_RATIO = 1.2
# Consecutive close frames with grounded posture required to enter GROUND.
# Slightly higher than MIN_GRAPPLING_THRESHOLD — ground transitions are slower
# than the per-frame noise that triggers a false clinch read.
MIN_GROUND_THRESHOLD = 5

# Number of frames to look back when determining takedown initiator
TAKEDOWN_LOOKBACK_FRAMES = 15

# Minimum hip drop (pixels) for a fighter to be considered the one being taken down
MIN_HIP_DROP_THRESHOLD = 30

# Strike detection thresholds
# Velocities are expressed as (fraction of attacker scale) per second — fps-invariant.
# Contact distances are expressed as fraction of defender scale — zoom-invariant.
PUNCH_VELOCITY_RATIO = 4.5      # wrist speed (scale/sec) to count as a punch
KICK_VELOCITY_RATIO = 6.0       # ankle speed (scale/sec) to count as a kick
ARM_EXTENSION_THRESHOLD = 140   # minimum elbow angle (degrees) for a straight punch (jab/cross)
# Bent-arm punch (hook/uppercut): elbow angle window — too straight = jab (handled above),
# too bent = not a punch at all.
PUNCH_BENT_ANGLE_MIN = 60      # degrees — below this is too folded to be a punch
PUNCH_BENT_ANGLE_MAX = 139     # degrees — above this falls into the straight path
LEG_EXTENSION_THRESHOLD = 130   # minimum knee angle (degrees) for a kick
STRIKE_COOLDOWN_FRAMES = 15     # frames to suppress re-detection after a strike
STRIKE_EXTENSION_FRAMES = 2     # consecutive frames angle must be held to confirm a strike
# In clinch/grappling the fighters are already in contact so the open-range contact
# gate is replaced by a directional gate (below); use a lower velocity threshold to
# catch short-range strikes (knees, dirty boxing).
GRAPPLING_PUNCH_VELOCITY_RATIO = 2.0
GRAPPLING_KICK_VELOCITY_RATIO  = 2.5

# --- Grappling strike gate (clinch / ground) ---
# In a clinch fighters are entangled, so raw proximity no longer discriminates a
# strike from pummeling / hand-fighting / gripping — the hands are near the
# opponent's torso either way. The discriminating signal is DIRECTION: a real short
# strike drives the end-effector toward a target zone (head or torso), whereas
# swimming for underhooks, framing and gripping move it laterally or pull it back.
# A grappling strike must satisfy BOTH a relaxed proximity sanity-check and a
# velocity-alignment-toward-target check.
GRAPPLING_HEAD_CONTACT_RATIO  = 0.60   # relaxed head proximity (fraction of defender scale)
GRAPPLING_TORSO_CONTACT_RATIO = 0.70   # relaxed torso proximity (fraction of defender scale)
# Cosine of the angle between the end-effector velocity and the vector to the target
# zone. 0.5 ≈ within 60° of driving straight at the target. Pummeling / gripping
# motions are lateral or pull away and fall below this.
GRAPPLING_STRIKE_DIRECTION_MIN = 0.5

# Keypoint confidence gating
# Joints below this confidence are treated as unreliable and their limb is skipped.
# Landed-vs-attempted: head recoil check after a candidate strike
# Check the opponent head velocity over this many frames after contact.
RECOIL_LOOKAHEAD_FRAMES = 4
# Head must move at least this many (scale/sec) to count as a recoil signal.
RECOIL_VELOCITY_RATIO   = 1.5

# One-Euro filter parameters for keypoint smoothing
ONE_EURO_MIN_CUTOFF = 1.5   # Hz — higher = less lag, more noise
ONE_EURO_BETA       = 0.05  # speed coefficient — higher = less lag on fast motion
ONE_EURO_D_CUTOFF   = 1.0   # Hz — cutoff for derivative low-pass

KEYPOINT_MIN_CONFIDENCE = 0.4
# Strike-relevant joint indices (COCO): head, shoulders, elbows, wrists, hips, knees, ankles.
# Frame is valid if both fighters have all of these confident, rather than all 17 keypoints.
STRIKE_KEYPOINT_INDICES = [0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
# Core trunk joints (COCO): nose, shoulders, hips. These alone give the torso
# centre (velocity baseline), torso rectangle + head centre (contact gate as the
# defender) and body scale. The relaxed bar for open-range striking requires only
# these confident — the punching arm is gated per-limb inside detect_strikes, so a
# blurred wrist no longer discards the whole frame. Legs/ankles, routinely occluded
# in a standing broadcast view, are not required.
STRIKING_CORE_KEYPOINT_INDICES = [0, 5, 6, 11, 12]

# Contact distance ratios (fraction of defender torso-length scale)
# These gate ACCEPTANCE — whether a strike landed near the opponent at all.
HEAD_CONTACT_RATIO = 0.45
TORSO_CONTACT_RATIO = 0.55
LEG_CONTACT_RATIO = 0.45

# --- Head zone geometry (head-vs-body classification) ---
# Once a punch is accepted, head-vs-body is decided by the nearest anatomical
# REGION: distance outside the head circle vs distance outside the torso
# rectangle (0 when inside either). The head circle is centred on the confident
# head keypoints; its radius is derived from the ear-to-ear span when both ears
# are confident, else from body scale, then clamped to a sane band of the scale.
HEAD_RADIUS_EAR_FACTOR   = 0.80   # head radius ≈ ear-to-ear span × this
HEAD_RADIUS_SCALE_RATIO  = 0.25   # fallback head radius as fraction of torso scale
HEAD_RADIUS_MIN_RATIO    = 0.15   # clamp: min head radius (fraction of scale)
HEAD_RADIUS_MAX_RATIO    = 0.35   # clamp: max head radius (fraction of scale)
# When no head keypoint is confident, estimate the head centre this far above the
# shoulder midpoint (fraction of torso scale).
HEAD_ABOVE_SHOULDER_RATIO = 0.45

# Fight segmentation thresholds (in seconds — converted to frames at runtime using detected fps)
MIN_FIGHT_END_GAP_SECS    = 45.0   # seconds of low fighter presence to end fight
MIN_ROUND_GAP_SECS        = 20.0   # seconds of low engagement to split rounds
ROUND_ENGAGEMENT_DISTANCE = 800    # horizontal center distance threshold for engagement (px)
MIN_ROUND_LENGTH_SECS     = 1.2    # minimum round duration in seconds
MIN_VALID_FRAME_RATIO     = 0.2    # minimum fraction of valid frames (ratio, not time)
MIN_FIGHT_DURATION_SECS   = 2.4    # minimum total fight duration in seconds

# Hysteresis windows for fight/round state machines (in seconds — converted at runtime)
FIGHT_PRESENCE_WINDOW_SECS  = 5.0  # sliding window for fight presence ratio
FIGHT_ENTER_RATIO           = 0.7  # ratio of both-present frames in window to enter fight
FIGHT_EXIT_RATIO            = 0.3  # ratio below which we begin counting fight-end gap
ROUND_ENGAGEMENT_WINDOW_SECS = 3.0 # sliding window for round engagement ratio
ROUND_ENGAGED_RATIO         = 0.6  # ratio of engaged frames in window to be in a round
ROUND_DISENGAGED_RATIO      = 0.2  # ratio below which we begin counting round-break gap

# Scoreboard overlay — ROI calibration (bottom-strip OCR)
SCOREBOARD_STRIP_Y_START = 0.62          # top of the bottom search strip (fraction of frame height)
SCOREBOARD_STRIP_SEARCH_FRAMES = 10      # frames sampled during strip OCR calibration
SCOREBOARD_ROI_PADDING = 20             # padding added around the detected ROI (px)

# Scoreboard overlay — OCR extraction
SCOREBOARD_OCR_SAMPLE_RATE_HZ = 2        # OCR samples per second
SCOREBOARD_OCR_MIN_CONFIDENCE = 0.7      # PaddleOCR line-level confidence floor
SCOREBOARD_OCR_UPSCALE = 3               # crop upscale factor before OCR
SCOREBOARD_SMOOTHING_WINDOW = 5          # sample window for round-number mode smoothing
SCOREBOARD_TIMER_MAX_BACKWARD_JUMP = 2   # max allowed timer increase (s) before rejection
SCOREBOARD_DEBUG_CROP_INTERVAL = 20      # save a debug crop every Nth sample

# Signal fusion weights (must sum to 1.0)
FUSION_WEIGHT_OCR = 0.70
FUSION_WEIGHT_DETECTION = 0.20
FUSION_WEIGHT_ENGAGEMENT = 0.10

# OCR signal snap: snap round boundary if within this many seconds of an OCR transition
OCR_BOUNDARY_SNAP_SECS = 1.5   # converted to frames at runtime using detected fps

# --- Fighter tracking (FighterTracker) ---
TRACK_MAX_FIGHTERS       = 2
TRACK_IOU_WEIGHT         = 0.6   # fraction of cost matrix from IoU term
TRACK_DISTANCE_WEIGHT    = 0.4   # fraction of cost matrix from centroid-distance term
TRACK_MAX_FRAMES_MISSING = 30    # frames a slot coasts before being pruned
CLINCH_IOU_THRESHOLD     = 0.3   # inter-fighter IoU above which velocity is frozen

# --- Glove-tape corner assignment ---
TAPE_PATCH_HALF          = 40    # base half-side of the wrist crop in px (radius)
WRIST_EDGE_MARGIN        = 10    # skip wrist if within this many px of frame border
TAPE_MIN_SATURATION      = 80    # HSV S floor (0-255) — drops skin / grey pixels
TAPE_MIN_VALUE           = 60    # HSV V floor (0-255) — drops black / dark pixels
RED_HUE_HIGH1            = 10    # red band 1: 0 .. HIGH1  (OpenCV hue 0-180)
RED_HUE_LOW2             = 170   # red band 2: LOW2 .. 180
BLUE_HUE_LOW             = 100
BLUE_HUE_HIGH            = 130
CORNER_MIN_TAPE_SAMPLES  = 200   # min total coloured pixels before trusting tape vote

# --- Appearance-anchored per-frame corner assignment ---
# Torso / shorts histogram sampling
TORSO_HIST_BINS               = 16    # hue histogram bins (OpenCV hue 0–180)
TORSO_MIN_SATURATION          = 50    # HSV S floor for torso pixels
TORSO_MIN_VALUE               = 40    # HSV V floor for torso pixels
TORSO_SAMPLE_MIN_PIXELS       = 150   # min pixels to trust a torso histogram

# Template bootstrap + per-frame assignment
CORNER_CLEAN_FRAME_MIN_TAPE   = 8     # per-frame combined tape px to qualify as a clean frame
CORNER_TEMPLATE_MIN_SEPARATION = 0.15 # separation below this → distrust appearance, use legacy
CORNER_TAPE_WEIGHT            = 0.6   # tape-cue weight in combined distance (sums to 1 with hist)
CORNER_HIST_WEIGHT            = 0.4   # torso-histogram weight
CORNER_HYSTERESIS_WEIGHT      = 0.5   # penalty added to any assignment that flips a slot's label
CORNER_SWAP_CONFIRM_FRAMES    = 4     # consecutive frames a flip must persist to be confirmed

# --- Grappling frame-validity relaxation ---
GRAPPLING_MIN_VISIBLE_KEYPOINTS = 6   # min confident strike-relevant joints for PARTIAL validity