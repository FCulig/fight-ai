from typing import List

from app.utils.db import run_db_query
from app.models.round import Round


def get_rounds(fight_id: int) -> List[Round]:
    def _query(session):
        return (
            session.query(Round)
            .filter(Round.fight_id == fight_id)
            .order_by(Round.round_number)
            .all()
        )

    return run_db_query(_query)
