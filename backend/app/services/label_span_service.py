from typing import List, Optional

from app.utils.db import run_db_query
from app.models.label_span import LabelSpan, LabelSpanCreate, LabelSpanUpdate
from app.models.round import Round


def get_label_spans(fight_id: int) -> List[LabelSpan]:
    def _query(session):
        # Human-verified round bounds are seeded from AI segmentation the first
        # time they're requested, so the labeller starts from a pre-filled
        # boundary instead of marking every round from scratch.
        has_round_spans = (
            session.query(LabelSpan)
            .filter(LabelSpan.fight_id == fight_id, LabelSpan.kind == "round")
            .first()
        ) is not None
        if not has_round_spans:
            rounds = (
                session.query(Round)
                .filter(Round.fight_id == fight_id)
                .order_by(Round.round_number)
                .all()
            )
            for r in rounds:
                session.add(LabelSpan(
                    fight_id=fight_id,
                    kind="round",
                    start_frame=r.start_frame,
                    end_frame=r.end_frame,
                    value=str(r.round_number),
                ))
            if rounds:
                session.commit()

        return (
            session.query(LabelSpan)
            .filter(LabelSpan.fight_id == fight_id)
            .order_by(LabelSpan.start_frame)
            .all()
        )

    return run_db_query(_query)


def create_label_span(fight_id: int, payload: LabelSpanCreate) -> LabelSpan:
    def _query(session):
        span = LabelSpan(
            fight_id=fight_id,
            kind=payload.kind,
            start_frame=payload.start_frame,
            end_frame=payload.end_frame,
            value=payload.value,
        )
        session.add(span)
        session.commit()
        session.refresh(span)
        return span

    return run_db_query(_query)


def update_label_span(fight_id: int, span_id: int, payload: LabelSpanUpdate) -> Optional[LabelSpan]:
    def _query(session):
        span = (
            session.query(LabelSpan)
            .filter(LabelSpan.id == span_id, LabelSpan.fight_id == fight_id)
            .first()
        )
        if span is None:
            return None
        if payload.start_frame is not None:
            span.start_frame = payload.start_frame
        if payload.end_frame is not None:
            span.end_frame = payload.end_frame
        if payload.value is not None:
            span.value = payload.value
        session.commit()
        session.refresh(span)
        return span

    return run_db_query(_query)


def delete_label_span(fight_id: int, span_id: int) -> bool:
    def _query(session):
        deleted = (
            session.query(LabelSpan)
            .filter(LabelSpan.id == span_id, LabelSpan.fight_id == fight_id)
            .delete()
        )
        session.commit()
        return deleted > 0

    return run_db_query(_query)


def rounds_fully_annotated(fight_id: int, session=None) -> bool:
    """Every detected round has a (possibly labeller-adjusted) `round`
    label_span — the precondition finish-labeling gates on."""
    def _query(s):
        round_count = s.query(Round).filter(Round.fight_id == fight_id).count()
        span_count = (
            s.query(LabelSpan)
            .filter(LabelSpan.fight_id == fight_id, LabelSpan.kind == "round")
            .count()
        )
        return round_count > 0 and span_count >= round_count

    if session is not None:
        return _query(session)
    return run_db_query(_query)
