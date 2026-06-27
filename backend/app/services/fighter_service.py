from typing import List, Optional

from sqlalchemy import or_

from app.utils.db import run_db_query
from app.models.fighter import Fighter, FighterCreate
from app.models.fight_event import FightEvent


def get_fighters(search: Optional[str] = None) -> List[Fighter]:
    def _query(session):
        q = session.query(Fighter)
        if search:
            like = f"%{search}%"
            q = q.filter(
                or_(
                    Fighter.first_name.ilike(like),
                    Fighter.last_name.ilike(like),
                    Fighter.nickname.ilike(like),
                )
            )
        return q.order_by(Fighter.last_name, Fighter.first_name).all()

    return run_db_query(_query)


def get_fighter_by_id(fighter_id: int) -> Optional[Fighter]:
    def _query(session):
        return session.query(Fighter).filter(Fighter.id == fighter_id).first()

    return run_db_query(_query)


def create_fighter(payload: FighterCreate) -> Fighter:
    def _query(session):
        fighter = Fighter(
            first_name=payload.first_name,
            last_name=payload.last_name,
            nickname=payload.nickname,
        )
        session.add(fighter)
        session.commit()
        session.refresh(fighter)
        return fighter

    return run_db_query(_query)


def get_events_by_fighter(
    fighter_id: int,
    action: Optional[str] = None,
    success: Optional[bool] = None,
) -> List[FightEvent]:
    """Cross-fight event query for a single fighter.

    ``action`` matches as a prefix (e.g. ``jab`` matches ``jab_head`` and
    ``jab_body``); ``success`` filters landed (True) / missed (False) strikes.
    """
    def _query(session):
        q = session.query(FightEvent).filter(FightEvent.fighter_id == fighter_id)
        if action:
            q = q.filter(FightEvent.action.ilike(f"{action}%"))
        if success is not None:
            q = q.filter(FightEvent.success.is_(success))
        return q.order_by(FightEvent.fight_id, FightEvent.frame).all()

    return run_db_query(_query)


def set_fight_corners(
    fight_id: int,
    red_fighter_id: Optional[int],
    blue_fighter_id: Optional[int],
) -> bool:
    """Assign corner fighters to a fight. Returns False if the fight is missing."""
    from app.models.fight import Fight

    def _query(session):
        fight = session.query(Fight).filter(Fight.id == fight_id).first()
        if fight is None:
            return False
        fight.red_fighter_id = red_fighter_id
        fight.blue_fighter_id = blue_fighter_id
        session.commit()
        return True

    return run_db_query(_query)
