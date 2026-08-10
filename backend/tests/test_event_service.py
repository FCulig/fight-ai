from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest

from app.utils import db
from app.models.fight import Fight  # noqa: F401 — registers the `fights` table for FK resolution
from app.models.fighter import Fighter  # noqa: F401 — registers the `fighters` table for FK resolution
from app.models.fight_event import FightEvent, FightEventCreate
from app.services import event_service


@pytest.fixture
def session_factory(monkeypatch):
    # use an in-memory SQLite database for the test
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db.Base.metadata.create_all(bind=engine)

    # patch the service's run_db_query helper to use the test session
    def fake_run_db_query(fn):
        with SessionLocal() as session:
            return fn(session)

    monkeypatch.setattr(event_service, "run_db_query", fake_run_db_query)
    return SessionLocal


def test_get_fight_events_returns_models(session_factory):
    SessionLocal = session_factory

    # insert a couple of events directly
    with SessionLocal() as session:
        session.add(FightEvent(frame=10, description="foo", fight_id=1))
        session.add(FightEvent(frame=20, description="bar", fight_id=1))
        session.commit()

    result = event_service.get_fight_events()
    assert isinstance(result, list)
    assert len(result) == 2
    assert isinstance(result[0], FightEvent)
    assert result[0].frame == 10
    assert result[1].description == "bar"


def test_create_event_persists_row(session_factory):
    payload = FightEventCreate(frame=42, description="red jab to the head", fighter_id=None, action="jab", success=True)

    created = event_service.create_event(fight_id=1, payload=payload)

    assert created.id is not None
    assert created.fight_id == 1
    assert created.frame == 42
    assert created.action == "jab"
    assert created.success is True

    result = event_service.get_fight_events()
    assert len(result) == 1
    assert result[0].description == "red jab to the head"


def test_delete_event_removes_row_and_reports_result(session_factory):
    payload = FightEventCreate(frame=1, description="Round 1 started", action="round_start")
    created = event_service.create_event(fight_id=1, payload=payload)

    assert event_service.delete_event(created.id) is True
    assert event_service.get_fight_events() == []
    assert event_service.delete_event(created.id) is False