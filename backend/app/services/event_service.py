from typing import List, Optional

from app.utils.db import run_db_query
from app.models.fight_event import FightEvent, FightEventCreate


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


def create_event(fight_id: int, payload: FightEventCreate) -> FightEvent:
    def _query(session):
        event = FightEvent(
            fight_id=fight_id,
            frame=payload.frame,
            description=payload.description,
            fighter_id=payload.fighter_id,
            action=payload.action,
            success=payload.success,
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        return event

    return run_db_query(_query)


def delete_event(event_id: int) -> bool:
    def _query(session):
        deleted = session.query(FightEvent).filter(FightEvent.id == event_id).delete()
        session.commit()
        return deleted > 0

    return run_db_query(_query)
