"""Load pipeline output from PostgreSQL into the evaluation label taxonomy.

PostgreSQL is the pipeline's only data store, so predictions are read straight
from ``fight_events`` / ``rounds`` — the harness scores exactly what the
pipeline persisted, not a re-derived copy.

Note on state events: ``fight_events.state`` is the structured source of
truth for a STRIKING/CLINCH/GROUND transition row. The free-text regex over
``description`` is kept only as a fallback for rows written before that
column existed — the pipeline itself always fills it in now.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from sqlalchemy import text

from database import SessionLocal

from .schema import PIPELINE_ACTION_MAP, Round, Strike

# "fighter_red threw a jab_head (landed)"
_STRIKE_RE = re.compile(r"^(fighter_red|fighter_blue)\s+threw\s+a\s+(\w+)")
# "Fight state changed to FightState.CLINCH, clinch initiated by fighter_red"
_STATE_RE = re.compile(r"FightState\.(\w+)")


@dataclass
class PredictedStrike(Strike):
    """A strike read from fight_events, carrying the raw pipeline action string.
    `fighter` is "unknown" when the fight had no corners assigned at upload."""
    action: str = ""


@dataclass
class StateChange:
    frame: int
    state: str


@dataclass
class Predictions:
    fight_id: int
    video: str
    fps: int
    frame_count: int = 0
    strikes: list[PredictedStrike] = field(default_factory=list)
    state_changes: list[StateChange] = field(default_factory=list)
    rounds: list[Round] = field(default_factory=list)
    # process_fight() seeds current_fight_state = FightState.STRIKING and only
    # writes an event when the state *changes*, so every frame before the first
    # recorded transition was predicted STRIKING. Scoring those as "no
    # prediction" would silently exclude the opening minutes of every fight.
    initial_state: str = "STRIKING"

    def state_at(self, frame: int) -> str:
        """State in effect at `frame`, from the most recent transition at or
        before it, falling back to the pipeline's initial state."""
        current = self.initial_state
        for sc in self.state_changes:
            if sc.frame > frame:
                break
            current = sc.state
        return current

    def in_any_round(self, frame: int) -> bool:
        return any(r.start <= frame <= r.end for r in self.rounds)


def lookup_fight(db, video: str) -> tuple[int, str, int, int]:
    """Resolve a video path/name to its fights row.

    Matches on the exact ``video_path`` first, then falls back to a filename
    match so `eval` works whether you pass `fight_videos/x.mp4` or just `x.mp4`.
    """
    row = db.execute(
        text("SELECT id, video_path, fps, width, height FROM fights "
             "WHERE video_path = :v"),
        {"v": str(video)},
    ).first()

    if row is None:
        stem = Path(video).name
        rows = db.execute(
            text("SELECT id, video_path, fps, width, height FROM fights "
                 "WHERE video_path LIKE :pat ORDER BY id"),
            {"pat": f"%{stem}"},
        ).all()
        if not rows:
            raise LookupError(
                f"No fights row for {video!r}. Run the pipeline on it first:\n"
                f"  python main.py {video}"
            )
        if len(rows) > 1:
            paths = ", ".join(r.video_path for r in rows)
            raise LookupError(
                f"{video!r} matches {len(rows)} fights rows ({paths}); "
                f"pass the exact video_path."
            )
        row = rows[0]

    return row.id, row.video_path, int(row.fps), 0


def load_predictions(video: str) -> Predictions:
    """Read every persisted event for a video and map it into the label taxonomy."""
    db = SessionLocal()
    try:
        fight_id, video_path, fps, _ = lookup_fight(db, video)
        return _load_predictions(db, fight_id, video_path, fps)
    finally:
        db.close()


def load_predictions_by_fight_id(fight_id: int) -> Predictions:
    """Same as `load_predictions`, but resolves by fight id directly — see
    `build_labels_by_fight_id` in labels_db.py for why: the fight whose
    predictions are being scored and the fight whose labels they're scored
    against don't share a `video_path`."""
    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT video_path, fps FROM fights WHERE id = :fid"),
            {"fid": fight_id},
        ).first()
        if row is None:
            raise LookupError(f"No fights row with id={fight_id}")
        return _load_predictions(db, fight_id, row.video_path, int(row.fps))
    finally:
        db.close()


def _load_predictions(db, fight_id: int, video_path: str, fps: int) -> Predictions:
    preds = Predictions(fight_id=fight_id, video=video_path, fps=fps)

    for r in db.execute(
        text("SELECT round_number, start_frame, end_frame FROM rounds "
             "WHERE fight_id = :fid ORDER BY round_number"),
        {"fid": fight_id},
    ):
        preds.rounds.append(
            Round(start=r.start_frame, end=r.end_frame, round=r.round_number)
        )

    # Current-code rows store `description = NULL` (only fight_end keeps one),
    # so the attacker's corner can only be recovered from `fighter_id`, which
    # process_fight resolved from this same fights row's red/blue_fighter_id.
    corners = db.execute(
        text("SELECT red_fighter_id, blue_fighter_id FROM fights WHERE id = :fid"),
        {"fid": fight_id},
    ).first()
    corner_by_fighter_id = {
        fighter_id: corner
        for fighter_id, corner in ((corners.red_fighter_id, "red"),
                                   (corners.blue_fighter_id, "blue"))
        if fighter_id is not None
    }

    rows = db.execute(
        text("SELECT frame, description, action, fighter_id, success, state FROM fight_events "
             "WHERE fight_id = :fid AND source = 'prediction' ORDER BY frame, id"),
        {"fid": fight_id},
    ).all()

    for row in rows:
        desc = row.description or ""

        m = _STRIKE_RE.match(desc)
        if m or row.action in PIPELINE_ACTION_MAP:
            if m:
                # Legacy row: the corner the pipeline wrote at the time, immune
                # to a later manual edit of the fights row's corner mapping.
                corner = "red" if m.group(1) == "fighter_red" else "blue"
            else:
                # NULL fighter_id means corners were unassigned at upload. The
                # strike still counts for detection, which ignores the corner
                # (see score.py) — dropping it would hide a real FP/TP.
                corner = corner_by_fighter_id.get(row.fighter_id, "unknown")
            action = row.action or m.group(2)
            family, target = PIPELINE_ACTION_MAP.get(action, ("punch", "unknown"))
            preds.strikes.append(PredictedStrike(
                frame=row.frame,
                fighter=corner,
                family=family,
                target=target,
                landed=row.success,
                action=action,
            ))
            continue

        if row.state:
            preds.state_changes.append(StateChange(frame=row.frame, state=row.state))
            continue

        # Fallback for rows written before the structured `state` column
        # existed.
        m = _STATE_RE.search(desc)
        if m:
            preds.state_changes.append(StateChange(frame=row.frame, state=m.group(1)))

    # frame_count: the highest frame the pipeline wrote a fighter box for.
    fc = db.execute(
        text("SELECT MAX(frame) AS mx FROM fighter_frames WHERE fight_id = :fid"),
        {"fid": fight_id},
    ).scalar()
    preds.frame_count = int(fc or 0)

    return preds
