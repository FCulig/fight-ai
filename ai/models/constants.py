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