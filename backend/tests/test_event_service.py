from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest

from app.utils import db
from app.models.fight import Fight  # noqa: F401 — registers the `fights` table for FK resolution
from app.models.fighter import Fighter  # noqa: F401 — registers the `fighters` table for FK resolution
from app.models.round import Round  # noqa: F401 — registers the `rounds` table for FK resolution
from app.models.fight_event import FightEvent, FightEventCreate, FightEventUpdate
from app.services import event_service


@pytest.fixture
def session_factory(monkeypatch):
    # use an in-memory SQLite database for the test
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    # Only the tables under test: other test modules import app.main, which
    # registers Postgres-only types (eval_runs' JSONB) that SQLite can't create.
    db.Base.metadata.create_all(
        bind=engine,
        tables=[Fight.__table__, Fighter.__table__, Round.__table__, FightEvent.__table__],
    )

    # patch the service's run_db_query helper to use the test session
    def fake_run_db_query(fn):
        with SessionLocal() as session:
            return fn(session)

    monkeypatch.setattr(event_service, "run_db_query", fake_run_db_query)
    return SessionLocal


def test_get_events_by_fight_returns_models(session_factory):
    SessionLocal = session_factory

    with SessionLocal() as session:
        session.add(FightEvent(frame=10, description="foo", fight_id=1, source="prediction", kind="point"))
        session.add(FightEvent(frame=20, description="bar", fight_id=1, source="prediction", kind="point"))
        session.commit()

    result = event_service.get_events_by_fight(1)
    assert isinstance(result, list)
    assert len(result) == 2
    assert isinstance(result[0], FightEvent)
    assert result[0].frame == 10
    assert result[1].description == "bar"


def test_get_events_by_fight_filters_by_source_and_kind(session_factory):
    SessionLocal = session_factory

    with SessionLocal() as session:
        session.add(FightEvent(frame=1, description="pred", fight_id=1, source="prediction", kind="point"))
        session.add(FightEvent(frame=2, description="label", fight_id=1, source="label", kind="point"))
        session.add(FightEvent(frame=3, fight_id=1, source="label", kind="round", value="1"))
        session.commit()

    predictions = event_service.get_events_by_fight(1, source="prediction")
    assert [e.description for e in predictions] == ["pred"]

    labels = event_service.get_events_by_fight(1, source="label", kind="point")
    assert [e.description for e in labels] == ["label"]

    spans = event_service.get_events_by_fight(1, source="label", kind="round")
    assert [e.value for e in spans] == ["1"]


def test_create_event_persists_label_row(session_factory):
    payload = FightEventCreate(frame=42, description="red jab to the head", action="jab", success=True)

    created = event_service.create_event(fight_id=1, payload=payload)

    assert created.id is not None
    assert created.fight_id == 1
    assert created.frame == 42
    assert created.action == "jab"
    assert created.success is True
    # create_event always writes source='label' — this is Annotate's only
    # write path, and the payload has no way to request 'prediction'.
    assert created.source == "label"
    assert created.kind == "point"

    result = event_service.get_events_by_fight(1)
    assert len(result) == 1
    assert result[0].description == "red jab to the head"


def test_create_event_persists_span_row(session_factory):
    payload = FightEventCreate(kind="corner_swap", frame=100, end_frame=None)

    created = event_service.create_event(fight_id=1, payload=payload)

    assert created.kind == "corner_swap"
    assert created.source == "label"
    assert created.description is None
    assert created.end_frame is None


def test_delete_event_removes_label_row_and_reports_result(session_factory):
    payload = FightEventCreate(frame=1, description="Round 1 started", action="round_start")
    created = event_service.create_event(fight_id=1, payload=payload)

    assert event_service.delete_event(fight_id=1, event_id=created.id) is True
    assert event_service.get_events_by_fight(1) == []
    assert event_service.delete_event(fight_id=1, event_id=created.id) is False


def test_delete_event_never_deletes_a_prediction_row(session_factory):
    SessionLocal = session_factory

    with SessionLocal() as session:
        pred = FightEvent(
            frame=5, description="fighter_red threw a jab_head (landed)",
            fight_id=1, source="prediction", kind="point", action="jab_head", success=True,
        )
        session.add(pred)
        session.commit()
        session.refresh(pred)
        pred_id = pred.id

    # The whole point of scoping the delete to source='label': the
    # label-editing API can never remove a pipeline-predicted row.
    assert event_service.delete_event(fight_id=1, event_id=pred_id) is False
    assert len(event_service.get_events_by_fight(1)) == 1


def test_update_event_updates_a_range_row(session_factory):
    created = event_service.create_event(
        fight_id=1, payload=FightEventCreate(kind="round", frame=1, end_frame=None, value="1"),
    )

    updated = event_service.update_event(
        fight_id=1, event_id=created.id,
        payload=FightEventUpdate(end_frame=500),
    )

    assert updated is not None
    assert updated.end_frame == 500
    assert updated.value == "1"


def test_update_event_rejects_a_point_row(session_factory):
    created = event_service.create_event(
        fight_id=1, payload=FightEventCreate(frame=1, description="jab to the head"),
    )

    result = event_service.update_event(
        fight_id=1, event_id=created.id, payload=FightEventUpdate(frame=2),
    )
    assert result is None


def test_rounds_fully_annotated(session_factory):
    SessionLocal = session_factory

    with SessionLocal() as session:
        session.add(Round(fight_id=1, round_number=1, start_frame=1, end_frame=100))
        session.add(Round(fight_id=1, round_number=2, start_frame=101, end_frame=200))
        session.commit()

    assert event_service.rounds_fully_annotated(1) is False

    event_service.create_event(fight_id=1, payload=FightEventCreate(kind="round", frame=1, end_frame=100, value="1"))
    assert event_service.rounds_fully_annotated(1) is False

    event_service.create_event(fight_id=1, payload=FightEventCreate(kind="round", frame=101, end_frame=200, value="2"))
    assert event_service.rounds_fully_annotated(1) is True


class TestFightEventCreateValidation:
    """SQLite (used in these tests) doesn't enforce the Postgres CHECK
    constraints added in d7e8f9a0b1c2, so the Pydantic validator is the only
    thing actually guarding these invariants under test."""

    def test_rejects_unknown_kind(self):
        with pytest.raises(ValueError):
            FightEventCreate(kind="not_a_kind", frame=1)

    def test_fight_end_requires_description(self):
        with pytest.raises(ValueError):
            FightEventCreate(kind="point", frame=1, action="fight_end")

    def test_other_point_actions_do_not_require_description(self):
        # Reconstructed client-side from action/target/corner instead —
        # see utils/describeEvent.ts.
        FightEventCreate(kind="point", frame=1, action="jab")

    def test_range_kind_does_not_require_description(self):
        FightEventCreate(kind="excluded", frame=1, end_frame=10)

    def test_rejects_invalid_corner(self):
        with pytest.raises(ValueError):
            FightEventCreate(frame=1, description="x", corner=2)

    def test_rejects_corner_on_state_action(self):
        with pytest.raises(ValueError):
            FightEventCreate(frame=1, description="x", action="state_ground", corner=0)


def _fight(session, fight_id, purpose):
    session.add(Fight(id=fight_id, video_path=f"v{fight_id}.mp4", fps=50, width=1280, height=720,
                      state="labeling_complete", purpose=purpose,
                      created_at=datetime(2026, 1, 1)))  # server default is Postgres now(), absent in SQLite


def test_set_verified_rejects_reference_fight(session_factory):
    SessionLocal = session_factory
    with SessionLocal() as session:
        _fight(session, 1, "reference")
        session.add(FightEvent(id=5, frame=10, fight_id=1, source="label", kind="point", action="jab"))
        session.commit()

    with pytest.raises(event_service.NotTrainingData):
        event_service.set_verified(1, 5, True)
    with pytest.raises(event_service.NotTrainingData):
        event_service.set_verified(1, 5, False)
    # clearing a stray verdict is still allowed
    assert event_service.set_verified(1, 5, None).is_verified is None


def test_set_verified_allows_training_data_fight(session_factory):
    SessionLocal = session_factory
    with SessionLocal() as session:
        _fight(session, 2, "training_data")
        session.add(FightEvent(id=6, frame=10, fight_id=2, source="label", kind="point", action="jab"))
        session.commit()

    assert event_service.set_verified(2, 6, True).is_verified is True
