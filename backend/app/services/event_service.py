from typing import List

from app.utils.db import run_db_query
from app.models.fight_event import FightEvent


def get_fight_events() -> List[FightEvent]:
    """Return all fight events from the database as SQLAlchemy model objects."""

    def _query(session):
        return session.query(FightEvent).all()

    return run_db_query(_query)
