"""Load pipeline output from PostgreSQL into the evaluation label taxonomy.

PostgreSQL is the pipeline's only data store, so predictions are read straight
from ``fight_events`` / ``rounds`` — the harness scores exactly what the
pipeline persisted, not a re-derived copy.

Note on state events: the pipeline records fight-state transitions only in the
free-text ``description`` column (``action`` is NULL for a STRIKING transition
and ``clinch_initiated`` / ``takedown_initiated`` otherwise), so the state has
to be recovered by regex. That is fragile — ``fight_events`` should grow a
structured ``state`` column. Until it does, this parser is the contract.
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
    """A strike read from fight_events, carrying the raw pipeline action string."""
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


def _lookup_fight(db, video: str) -> tuple[int, str, int, int]:
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
        fight_id, video_path, fps, _ = _lookup_fight(db, video)

        preds = Predictions(fight_id=fight_id, video=video_path, fps=fps)

        for r in db.execute(
            text("SELECT round_number, start_frame, end_frame FROM rounds "
                 "WHERE fight_id = :fid ORDER BY round_number"),
            {"fid": fight_id},
        ):
            preds.rounds.append(
                Round(start=r.start_frame, end=r.end_frame, round=r.round_number)
            )

        rows = db.execute(
            text("SELECT frame, description, action, success FROM fight_events "
                 "WHERE fight_id = :fid ORDER BY frame, id"),
            {"fid": fight_id},
        ).all()

        for row in rows:
            desc = row.description or ""

            m = _STRIKE_RE.match(desc)
            if m:
                corner = "red" if m.group(1) == "fighter_red" else "blue"
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
    finally:
        db.close()
