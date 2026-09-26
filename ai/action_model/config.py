"""Window/taxonomy constants for the skeleton action model.

Kept separate from models/constants.py: those are pipeline thresholds
(including the strike model's peak picking), these define the model's input
contract. Changing anything here
invalidates every saved checkpoint — the values are copied into each
checkpoint's metadata so inference can refuse a mismatch.
"""

# Strike families the model predicts, index 0 reserved for "no strike".
# Same vocabulary as eval/schema.py's SPECIFIC_FAMILIES minus `elbow` (no
# labels exist yet), via eval/labels_db.py's LABEL_FAMILY_MAP — so hand-
# agnostic: left/right hooks are both `hook`, jab/cross are lead/rear.
CLASSES = ("none", "jab", "cross", "hook", "uppercut", "kick", "knee")
TARGETS = ("head", "body", "leg")

# The window is sampled on a fixed time grid, not in frames, so 24 fps and
# 50 fps fights produce identically-shaped tensors with the same meaning.
SAMPLE_HZ = 25
WINDOW_SECS = 1.2                                # plan: "~1s centred on the labelled frame"
WINDOW_STEPS = int(round(WINDOW_SECS * SAMPLE_HZ)) + 1   # 31 samples, centre at index 15
# Extra samples each side so training can randomly shift the centre — the
# labelled frame is a human click, accurate to a few frames at best.
JITTER_STEPS = 3

N_JOINTS = 17
# COCO left/right joint pairs, swapped when a window is mirrored.
FLIP_PAIRS = ((1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12), (13, 14), (15, 16))
# Normalised coordinates are clipped here: a hallucinated joint far off the
# body should not dominate a batch.
COORD_CLIP = 8.0

# Per timestep, per fighter: 17 x (x, y, conf) + present flag. Attacker first.
PERSON_CHANNELS = N_JOINTS * 3 + 1
IN_CHANNELS = 2 * PERSON_CHANNELS

# Negative ("none") sampling. A window is only a negative if the same corner
# has no hand label of ANY verification state within this radius — unreviewed
# and declined labels may still be real strikes.
NEG_EXCLUSION_SECS = 1.0
RANDOM_NEGATIVES_PER_POSITIVE = 1.0
