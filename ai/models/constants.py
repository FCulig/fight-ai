LABEL_ID = {
    "fighter_red": 0,
    "fighter_blue": 1,
    "referee": 2
}

# Mininum number of frames for which delta distance needs to hold value in order for grappling to start
MIN_GRAPPLING_THRESHOLD = 3

# Distance threshold to determine if fighters are grappling
DISTANCE_GRAPPLING_THRESHOLD = 20

# Number of frames to look back when determining takedown initiator
TAKEDOWN_LOOKBACK_FRAMES = 15

# Minimum hip drop (pixels) for a fighter to be considered the one being taken down
MIN_HIP_DROP_THRESHOLD = 30

# Strike detection thresholds
PUNCH_VELOCITY_THRESHOLD = 15   # pixels/frame for wrist to count as a punch
KICK_VELOCITY_THRESHOLD = 20    # pixels/frame for ankle to count as a kick
ARM_EXTENSION_THRESHOLD = 140   # minimum elbow angle (degrees) for a punch
LEG_EXTENSION_THRESHOLD = 130   # minimum knee angle (degrees) for a kick
STRIKE_COOLDOWN_FRAMES = 15     # frames to suppress re-detection after a strike
STRIKE_EXTENSION_FRAMES = 2    # consecutive frames angle must be held to confirm a strike

# Contact distance thresholds (pixels) for confirming a strike landed
HEAD_CONTACT_THRESHOLD = 50
TORSO_CONTACT_THRESHOLD = 60
LEG_CONTACT_THRESHOLD = 50

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