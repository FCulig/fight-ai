from typing import List, Optional

from app.utils.db import run_db_query
from app.models.fighter_frame import FighterFrame


def get_fighter_frames(
    fight_id: int, start_frame: Optional[int] = None, end_frame: Optional[int] = None,
) -> List[FighterFrame]:
    """`start_frame`/`end_frame` (1-based, inclusive) narrow this to a window
    instead of the whole fight — a full fight's keypoints run into the tens
    of MB (see frontend/CLAUDE.md's `useFighterFrames` convention), which is
    fine for Player/Annotate's free-scrub timeline but wasteful for
    ClipPlayer's ~0.6s review clip. `ix_fighter_frames_fight_frame` covers
    `(fight_id, frame)`, so this stays index-only regardless of fight length."""
    def _query(session):
        q = session.query(FighterFrame).filter(FighterFrame.fight_id == fight_id)
        if start_frame is not None:
            q = q.filter(FighterFrame.frame >= start_frame)
        if end_frame is not None:
            q = q.filter(FighterFrame.frame <= end_frame)
        return q.order_by(FighterFrame.frame).all()

    return run_db_query(_query)
