from typing import List

from app.utils.db import run_db_query
from app.models.label_event import LabelEvent, LabelEventCreate


def get_label_events(fight_id: int) -> List[LabelEvent]:
    def _query(session):
        return (
            session.query(LabelEvent)
            .filter(LabelEvent.fight_id == fight_id)
            .order_by(LabelEvent.frame)
            .all()
        )

    return run_db_query(_query)


def create_label_event(fight_id: int, payload: LabelEventCreate) -> LabelEvent:
    def _query(session):
        event = LabelEvent(
            fight_id=fight_id,
            frame=payload.frame,
            description=payload.description,
            corner=payload.corner,
            action=payload.action,
            target=payload.target,
            success=payload.success,
            labeler=payload.labeler,
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        return event

    return run_db_query(_query)


def delete_label_event(fight_id: int, event_id: int) -> bool:
    def _query(session):
        deleted = (
            session.query(LabelEvent)
            .filter(LabelEvent.id == event_id, LabelEvent.fight_id == fight_id)
            .delete()
        )
        session.commit()
        return deleted > 0

    return run_db_query(_query)
