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