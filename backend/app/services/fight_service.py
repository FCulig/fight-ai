from typing import List

from sqlalchemy import text
from app.utils.db import run_db_query
from app.models.fight import Fight
from app.models.fighter import Fighter


def _attach_fighter_names(session, fights: list[Fight]) -> list[Fight]:
    fighter_ids = set()
    for f in fights:
        if f.red_fighter_id:
            fighter_ids.add(f.red_fighter_id)
        if f.blue_fighter_id:
            fighter_ids.add(f.blue_fighter_id)
    if not fighter_ids:
        return fights
    rows = session.query(Fighter.id, Fighter.first_name, Fighter.last_name).filter(
        Fighter.id.in_(fighter_ids)
    ).all()
    names = {r.id: f"{r.first_name} {r.last_name}" for r in rows}
    for f in fights:
        f.red_fighter_name = names.get(f.red_fighter_id)
        f.blue_fighter_name = names.get(f.blue_fighter_id)
    return fights


def get_all_fights() -> List[Fight]:
    def _query(session):
        fights = session.query(Fight).order_by(Fight.id).all()
        return _attach_fighter_names(session, fights)

    return run_db_query(_query)


def get_processed_fights() -> List[Fight]:
    def _query(session):
        fights = session.query(Fight).filter(Fight.processed.is_(True)).order_by(Fight.id).all()
        return _attach_fighter_names(session, fights)

    return run_db_query(_query)


def get_fight_by_id(fight_id: int) -> Fight | None:
    def _query(session):
        fight = session.query(Fight).filter(Fight.id == fight_id).first()
        if fight:
            _attach_fighter_names(session, [fight])
        return fight

    return run_db_query(_query)


def create_fight(
    video_path: str,
    fps: int,
    width: int,
    height: int,
    red_fighter_id: int | None = None,
    blue_fighter_id: int | None = None,
) -> Fight:
    def _query(session):
        fight = Fight(
            video_path=video_path,
            fps=fps,
            width=width,
            height=height,
            red_fighter_id=red_fighter_id,
            blue_fighter_id=blue_fighter_id,
        )
        session.add(fight)
        session.commit()
        session.refresh(fight)
        _attach_fighter_names(session, [fight])
        return fight

    return run_db_query(_query)


def delete_fight(fight_id: int) -> str | None:
    def _query(session):
        result = session.execute(
            text("DELETE FROM fights WHERE id = :id RETURNING video_path"),
            {"id": fight_id},
        )
        session.commit()
        row = result.fetchone()
        return row[0] if row else None

    return run_db_query(_query)
