from enum import Enum

class FightState(Enum):
    STRIKING = 1   # standing, at range
    CLINCH   = 2   # within grapple distance, both fighters standing
    GROUND   = 3   # within grapple distance, at least one fighter on the ground


# States in which the fighters are entangled (clinch or ground). Used wherever
# the old binary GRAPPLING bucket was checked — clinch-strike detection,
# contact-gate skipping, etc.
GRAPPLING_STATES = frozenset({FightState.CLINCH, FightState.GROUND})
