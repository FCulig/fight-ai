from typing import List

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


def delete_fight(fight_id: int) -> bool:
    def _query(session):
        rows_deleted = session.query(Fight).filter(Fight.id == fight_id).delete()
        session.commit()
        return rows_deleted > 0

    return run_db_query(_query)
