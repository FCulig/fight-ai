from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest

from app.utils import db
from app.models.fight_event import FightEvent
from app.services import event_service


def test_get_fight_events_returns_models(monkeypatch):
    # use an in-memory SQLite database for the test
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db.Base.metadata.create_all(bind=engine)

    # patch the service's run_db_query helper to use the test session
    def fake_run_db_query(fn):
        with SessionLocal() as session:
            return fn(session)

    monkeypatch.setattr(event_service, "run_db_query", fake_run_db_query)

    # insert a couple of events directly
    with SessionLocal() as session:
        session.add(FightEvent(frame=10, description="foo"))
        session.add(FightEvent(frame=20, description="bar"))
        session.commit()

    result = event_service.get_fight_events()
    assert isinstance(result, list)
    assert len(result) == 2
    assert isinstance(result[0], FightEvent)
    assert result[0].frame == 10
    assert result[1].description == "bar"