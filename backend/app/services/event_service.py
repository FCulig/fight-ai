from typing import List, Optional

from app.utils.db import run_db_query
from app.models.fight_event import FightEvent, FightEventCreate, FightEventUpdate
from app.models.fight import Fight
from app.models.round import Round


class NotTrainingData(Exception):
    """A QA verdict was sent for an event on a fight that isn't
    `purpose='training_data'`. `reference` fights are held-out ground truth
    and never go through QA — see useTrainingDataEvents.ts."""


def get_events_by_fight(
    fight_id: int,
    fighter_id: Optional[int] = None,
    action: Optional[str] = None,
    success: Optional[bool] = None,
    kind: Optional[str] = None,
    source: Optional[str] = None,
) -> List[FightEvent]:
    def _query(session):
        if source == "label" and (kind is None or kind == "round"):
            _ensure_round_events_seeded(session, fight_id)

        q = session.query(FightEvent).filter(FightEvent.fight_id == fight_id)
        if fighter_id is not None:
            q = q.filter(FightEvent.fighter_id == fighter_id)
        if action:
            q = q.filter(FightEvent.action.ilike(f"{action}%"))
        if success is not None:
            q = q.filter(FightEvent.success.is_(success))
        if kind is not None:
            q = q.filter(FightEvent.kind == kind)
        if source is not None:
            q = q.filter(FightEvent.source == source)
        return q.order_by(FightEvent.frame).all()

    return run_db_query(_query)


def _ensure_round_events_seeded(session, fight_id: int) -> None:
    """Human-verified round bounds are seeded from AI segmentation the first
    time a fight's hand labels are fetched, so the labeller starts from a
    pre-filled boundary instead of marking every round from scratch. Must
    only ever run for a source='label' fetch — an ai_labeled fight's Player
    fetch (source='prediction') must never trigger this."""
    has_round_events = (
        session.query(FightEvent)
        .filter(
            FightEvent.fight_id == fight_id,
            FightEvent.source == "label",
            FightEvent.kind == "round",
        )
        .first()
    ) is not None
    if has_round_events:
        return

    rounds = (
        session.query(Round)
        .filter(Round.fight_id == fight_id)
        .order_by(Round.round_number)
        .all()
    )
    for r in rounds:
        session.add(FightEvent(
            fight_id=fight_id,
            source="label",
            kind="round",
            frame=r.start_frame,
            end_frame=r.end_frame,
            value=str(r.round_number),
        ))
    if rounds:
        session.commit()


def create_event(fight_id: int, payload: FightEventCreate) -> FightEvent:
    def _query(session):
        event = FightEvent(
            fight_id=fight_id,
            source="label",
            kind=payload.kind,
            frame=payload.frame,
            end_frame=payload.end_frame,
            description=payload.description,
            corner=payload.corner,
            action=payload.action,
            target=payload.target,
            success=payload.success,
            value=payload.value,
            labeler=payload.labeler,
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        return event

    return run_db_query(_query)


def update_event(fight_id: int, event_id: int, payload: FightEventUpdate) -> Optional[FightEvent]:
    def _query(session):
        event = (
            session.query(FightEvent)
            .filter(
                FightEvent.id == event_id,
                FightEvent.fight_id == fight_id,
                FightEvent.source == "label",
                FightEvent.kind != "point",
            )
            .first()
        )
        if event is None:
            return None
        if payload.frame is not None:
            event.frame = payload.frame
        if payload.end_frame is not None:
            event.end_frame = payload.end_frame
        if payload.value is not None:
            event.value = payload.value
        session.commit()
        session.refresh(event)
        return event

    return run_db_query(_query)


def set_verified(fight_id: int, event_id: int, is_verified: Optional[bool]) -> Optional[FightEvent]:
    """Training Data QA's write path — independent of `update_event` (which
    is span-only, `kind != 'point'`) since a verdict is exactly the opposite
    scope: it only ever applies to a hand-labelled point event."""
    def _query(session):
        event = (
            session.query(FightEvent)
            .filter(
                FightEvent.id == event_id,
                FightEvent.fight_id == fight_id,
                FightEvent.source == "label",
                FightEvent.kind == "point",
            )
            .first()
        )
        if event is None:
            return None
        # Clearing (None) is always allowed so a stray verdict can be undone;
        # setting one is training_data-only.
        if is_verified is not None:
            purpose = session.query(Fight.purpose).filter(Fight.id == fight_id).scalar()
            if purpose != "training_data":
                raise NotTrainingData(f"fight {fight_id} is '{purpose}', only training_data fights are QA'd")
        event.is_verified = is_verified
        session.commit()
        session.refresh(event)
        return event

    return run_db_query(_query)


def reclassify_event(
    fight_id: int, event_id: int, action: str, target: Optional[str], success: Optional[bool],
) -> Optional[FightEvent]:
    """Training Data QA's strike-retyping write path — same source='label'
    kind='point' scope as set_verified, since only a strike-shaped point
    event has an action/target worth correcting. Deliberately leaves
    `corner`/`is_verified` untouched: retyping a strike doesn't change who
    threw it or reset a verdict already given on the clip."""
    def _query(session):
        event = (
            session.query(FightEvent)
            .filter(
                FightEvent.id == event_id,
                FightEvent.fight_id == fight_id,
                FightEvent.source == "label",
                FightEvent.kind == "point",
            )
            .first()
        )
        if event is None:
            return None
        event.action = action
        event.target = target
        event.success = success
        session.commit()
        session.refresh(event)
        return event

    return run_db_query(_query)


def delete_event(fight_id: int, event_id: int) -> bool:
    def _query(session):
        # source='label' is the single most important guard in this
        # service: it makes it impossible for the Annotate delete endpoint
        # to ever remove a pipeline-predicted row.
        deleted = (
            session.query(FightEvent)
            .filter(
                FightEvent.id == event_id,
                FightEvent.fight_id == fight_id,
                FightEvent.source == "label",
            )
            .delete()
        )
        session.commit()
        return deleted > 0

    return run_db_query(_query)


def rounds_fully_annotated(fight_id: int, session=None) -> bool:
    """Every detected round has a (possibly labeller-adjusted) `round`-kind
    label event — the precondition finish-labeling gates on."""
    def _query(s):
        round_count = s.query(Round).filter(Round.fight_id == fight_id).count()
        event_count = (
            s.query(FightEvent)
            .filter(
                FightEvent.fight_id == fight_id,
                FightEvent.source == "label",
                FightEvent.kind == "round",
            )
            .count()
        )
        return round_count > 0 and event_count >= round_count

    if session is not None:
        return _query(session)
    return run_db_query(_query)
