from enum import Enum


class FightProcessingState(str, Enum):
    QUEUED      = "queued"
    DETECTING   = "detecting"
    TRACKING    = "tracking"
    POSE        = "pose"
    CORNERS     = "corners"
    SCOREBOARD  = "scoreboard"
    SEGMENTING  = "segmenting"
    ANALYZING   = "analyzing"
    COMPLETED   = "completed"
    FAILED      = "failed"
