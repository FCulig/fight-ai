from enum import Enum


class FightProcessingState(str, Enum):
    VALIDATING  = "validating"
    INVALID     = "invalid"
    QUEUED      = "queued"
    DETECTING   = "detecting"
    TRACKING    = "tracking"
    POSE        = "pose"
    CORNERS     = "corners"
    SCOREBOARD  = "scoreboard"
    SEGMENTING  = "segmenting"
    ANALYZING   = "analyzing"
    COMPLETED   = "completed"
    LABELING_IN_PROGRESS = "labeling_in_progress"
    LABELING_COMPLETE    = "labeling_complete"
    FAILED      = "failed"
