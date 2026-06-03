from typing import List

from app.utils.db import run_db_query
from app.models.fight_event import FightEvent


def get_fight_events() -> List[FightEvent]:
    def _query(session):
        return session.query(FightEvent).all()

    return run_db_query(_query)


def get_events_by_fight(fight_id: int) -> List[FightEvent]:
    def _query(session):
        return (
            session.query(FightEvent)
            .filter(FightEvent.fight_id == fight_id)
            .order_by(FightEvent.frame)
            .all()
        )

    return run_db_query(_query)
