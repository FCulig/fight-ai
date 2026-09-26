"""Builds training/validation windows from Postgres for the skeleton action model.

The join is fight_events(F, corner) -> fighter_frames(F', corner) for F' in a
window around F. `corner` is a track-slot pointer on BOTH sides (the labeller
clicks the overlay box), so corner_swap spans are deliberately NOT applied
here — flipping would attach the label to the other fighter's skeleton. See
eval/schema.py's FightLabels.corner_swaps and memory
"label-events-corner-is-box-not-person".

Window construction itself lives in windows.py, shared with inference.
"""

from dataclasses import dataclass, field

import numpy as np
from sqlalchemy import text

from eval.labels_db import LABEL_FAMILY_MAP

from .config import (
    CLASSES, IN_CHANNELS, NEG_EXCLUSION_SECS, RANDOM_NEGATIVES_PER_POSITIVE, TARGETS,
)
from .windows import TOTAL_STEPS, Track, build_window, empty_tracks, set_frame

FAMILY_INDEX = {name: i for i, name in enumerate(CLASSES)}
TARGET_INDEX = {name: i for i, name in enumerate(TARGETS)}

# Hand-label strike actions, i.e. everything LABEL_FAMILY_MAP knows whose
# family the model has a class for (clinch_punch/ground_punch -> `punch` and
# `elbow` have none yet and are skipped, never silently relabelled).
STRIKE_ACTIONS = tuple(a for a, fam in LABEL_FAMILY_MAP.items() if fam in FAMILY_INDEX)
ALL_LABEL_STRIKE_ACTIONS = tuple(LABEL_FAMILY_MAP)

# The training set, exactly as agreed: QA-confirmed hand labels on fights
# uploaded as training data. `is_verified IS TRUE` excludes both declined
# (False) and not-yet-reviewed (NULL) rows.
TRAINING_EVENTS_SQL = """
    SELECT e.id, e.fight_id, e.frame, e.corner, e.action, e.target
    FROM fight_events e JOIN fights f ON f.id = e.fight_id
    WHERE f.purpose = 'training_data'
      AND e.source = 'label' AND e.kind = 'point'
      AND e.is_verified IS TRUE
      AND e.corner IS NOT NULL
    ORDER BY e.fight_id, e.frame, e.id
"""

# Validation only, never trained on: every hand-labelled strike on a
# `reference` fight. Reference labels are ground truth as labelled — QA does
# not apply to them (the QA page and backend both refuse), so `is_verified`
# is deliberately not consulted here.
REFERENCE_EVENTS_SQL = """
    SELECT e.id, e.fight_id, e.frame, e.corner, e.action, e.target
    FROM fight_events e JOIN fights f ON f.id = e.fight_id
    WHERE f.purpose = 'reference' AND f.labeled_at IS NOT NULL
      AND e.source = 'label' AND e.kind = 'point'
      AND e.corner IS NOT NULL
    ORDER BY e.fight_id, e.frame, e.id
"""


@dataclass
class FightData:
    fight_id: int
    fps: int
    tracks: dict[int, Track]
    rounds: list[tuple[int, int]]
    excluded: list[tuple[int, int]]
    # corner -> sorted frames of every hand-labelled strike, any QA state
    label_frames: dict[int, np.ndarray]


@dataclass
class Samples:
    x: list[np.ndarray] = field(default_factory=list)
    family: list[int] = field(default_factory=list)
    target: list[int] = field(default_factory=list)      # -1 = no target
    fight_id: list[int] = field(default_factory=list)
    frame: list[int] = field(default_factory=list)
    corner: list[int] = field(default_factory=list)
    origin: list[str] = field(default_factory=list)      # label | hard_neg | rand_neg
    event_id: list[int] = field(default_factory=list)    # -1 for negatives

    def add(self, x, family, target, fight_id, frame, corner, origin, event_id=-1):
        self.x.append(x)
        self.family.append(family)
        self.target.append(target)
        self.fight_id.append(fight_id)
        self.frame.append(frame)
        self.corner.append(corner)
        self.origin.append(origin)
        self.event_id.append(event_id)

    def to_arrays(self) -> dict[str, np.ndarray]:
        return {
            "x": np.stack(self.x).astype(np.float32) if self.x
                 else np.zeros((0, IN_CHANNELS, TOTAL_STEPS), np.float32),
            "family": np.array(self.family, np.int64),
            "target": np.array(self.target, np.int64),
            "fight_id": np.array(self.fight_id, np.int64),
            "frame": np.array(self.frame, np.int64),
            "corner": np.array(self.corner, np.int64),
            "origin": np.array(self.origin),
            "event_id": np.array(self.event_id, np.int64),
        }


# --- loading ---------------------------------------------------------------

def load_fight(db, fight_id: int) -> FightData:
    fps = int(db.execute(text("SELECT fps FROM fights WHERE id = :f"), {"f": fight_id}).scalar())
    max_frame = int(db.execute(
        text("SELECT COALESCE(MAX(frame), 0) FROM fighter_frames WHERE fight_id = :f"),
        {"f": fight_id},
    ).scalar())

    tracks = empty_tracks(max_frame)
    rows = db.execute(
        text("SELECT frame, corner, x1, y1, x2, y2, keypoints FROM fighter_frames "
             "WHERE fight_id = :f AND corner IN (0, 1) AND keypoints IS NOT NULL"),
        {"f": fight_id},
    )
    for r in rows:
        set_frame(tracks, r.frame, r.corner, r.keypoints, (r.x1, r.y1, r.x2, r.y2))

    def spans(kind):
        return [
            (r.frame, r.end_frame) for r in db.execute(
                text("SELECT frame, end_frame FROM fight_events WHERE fight_id = :f "
                     "AND source = 'label' AND kind = :k AND end_frame IS NOT NULL"),
                {"f": fight_id, "k": kind},
            )
        ]

    label_frames = {0: [], 1: []}
    for r in db.execute(
        text("SELECT frame, corner FROM fight_events WHERE fight_id = :f "
             "AND source = 'label' AND kind = 'point' AND corner IS NOT NULL "
             "AND action = ANY(:acts)"),
        {"f": fight_id, "acts": list(ALL_LABEL_STRIKE_ACTIONS)},
    ):
        label_frames[r.corner].append(r.frame)

    return FightData(
        fight_id=fight_id, fps=fps, tracks=tracks,
        rounds=spans("round"), excluded=spans("excluded"),
        label_frames={c: np.array(sorted(v), np.int64) for c, v in label_frames.items()},
    )


# --- sample assembly -------------------------------------------------------

def _near_label(fight: FightData, corner: int, frame: int) -> bool:
    lf = fight.label_frames[corner]
    if len(lf) == 0:
        return False
    radius = NEG_EXCLUSION_SECS * fight.fps
    i = np.searchsorted(lf, frame)
    return any(0 <= j < len(lf) and abs(lf[j] - frame) <= radius for j in (i - 1, i))


def _negative_ok(fight: FightData, corner: int, frame: int) -> bool:
    if fight.rounds and not any(s <= frame <= e for s, e in fight.rounds):
        return False
    if any(s <= frame <= e for s, e in fight.excluded):
        return False
    return not _near_label(fight, corner, frame)


def add_fight_samples(samples: Samples, fight: FightData, events, rng: np.random.Generator,
                      negatives: bool = True) -> dict:
    """Append one fight's positives (from `events`) plus its negatives.

    Negatives come in two kinds, both needed because inference will run on
    both fighters at every moment:
      - hard_neg: the *opponent* at each labelled frame, unless the opponent
        has a label of their own nearby (a counter). Teaches "being hit is
        not striking".
      - rand_neg: random in-round moments with no label for that corner
        within NEG_EXCLUSION_SECS.
    """
    stats = {"positives": 0, "skipped_no_skeleton": 0, "skipped_class": 0,
             "hard_neg": 0, "rand_neg": 0}
    for e in events:
        family = LABEL_FAMILY_MAP.get(e.action)
        if family not in FAMILY_INDEX:
            stats["skipped_class"] += 1
            continue
        x = build_window(fight.tracks, fight.fps, e.frame, e.corner)
        if x is None:
            stats["skipped_no_skeleton"] += 1
            continue
        target = TARGET_INDEX.get(e.target, -1) if e.target else -1
        samples.add(x, FAMILY_INDEX[family], target, fight.fight_id, e.frame, e.corner, "label", e.id)
        stats["positives"] += 1

        if negatives:
            other = 1 - e.corner
            if not _near_label(fight, other, e.frame):
                xn = build_window(fight.tracks, fight.fps, e.frame, other)
                if xn is not None:
                    samples.add(xn, 0, -1, fight.fight_id, e.frame, other, "hard_neg")
                    stats["hard_neg"] += 1

    if negatives and stats["positives"]:
        want = int(round(stats["positives"] * RANDOM_NEGATIVES_PER_POSITIVE))
        spans = fight.rounds or [(0, len(fight.tracks[0].present) - 1)]
        tries = 0
        while stats["rand_neg"] < want and tries < want * 50:
            tries += 1
            s, e = spans[rng.integers(len(spans))]
            frame = int(rng.integers(s, e + 1))
            corner = int(rng.integers(2))
            if not _negative_ok(fight, corner, frame):
                continue
            xn = build_window(fight.tracks, fight.fps, frame, corner)
            if xn is None:
                continue
            samples.add(xn, 0, -1, fight.fight_id, frame, corner, "rand_neg")
            stats["rand_neg"] += 1
    return stats


def build_dataset(db, events_sql: str, seed: int = 0, negatives: bool = True):
    """Returns (arrays, per-fight stats) for every fight the query touches."""
    rng = np.random.default_rng(seed)
    events = db.execute(text(events_sql)).all()
    by_fight: dict[int, list] = {}
    for e in events:
        by_fight.setdefault(e.fight_id, []).append(e)

    samples = Samples()
    stats = {}
    for fight_id, fight_events in sorted(by_fight.items()):
        fight = load_fight(db, fight_id)
        stats[fight_id] = {"fps": fight.fps, **add_fight_samples(samples, fight, fight_events, rng, negatives)}
    return samples.to_arrays(), stats
