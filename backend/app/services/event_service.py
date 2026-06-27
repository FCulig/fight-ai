from typing import List, Optional

from app.utils.db import run_db_query
from app.models.fight_event import FightEvent


def get_fight_events() -> List[FightEvent]:
    def _query(session):
        return session.query(FightEvent).all()

    return run_db_query(_query)


def get_events_by_fight(
    fight_id: int,
    fighter_id: Optional[int] = None,
    action: Optional[str] = None,
    success: Optional[bool] = None,
) -> List[FightEvent]:
    def _query(session):
        q = session.query(FightEvent).filter(FightEvent.fight_id == fight_id)
        if fighter_id is not None:
            q = q.filter(FightEvent.fighter_id == fighter_id)
        if action:
            q = q.filter(FightEvent.action.ilike(f"{action}%"))
        if success is not None:
            q = q.filter(FightEvent.success.is_(success))
        return q.order_by(FightEvent.frame).all()

    return run_db_query(_query)
