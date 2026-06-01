from typing import List

from app.utils.db import run_db_query
from app.models.fighter_frame import FighterFrame


def get_fighter_frames(fight_id: int) -> List[FighterFrame]:
    def _query(session):
        return (
            session.query(FighterFrame)
            .filter(FighterFrame.fight_id == fight_id)
            .order_by(FighterFrame.frame)
            .all()
        )

    return run_db_query(_query)
