from typing import List

from sqlalchemy import text

from app.utils.db import run_db_query
from app.models.fight import Fight


def get_all_fights() -> List[Fight]:
    def _query(session):
        return session.query(Fight).order_by(Fight.id).all()

    return run_db_query(_query)


def get_processed_fights() -> List[Fight]:
    def _query(session):
        return session.query(Fight).filter(Fight.processed.is_(True)).order_by(Fight.id).all()

    return run_db_query(_query)


def get_fight_by_id(fight_id: int) -> Fight | None:
    def _query(session):
        return session.query(Fight).filter(Fight.id == fight_id).first()

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
