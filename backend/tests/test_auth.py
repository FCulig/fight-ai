import os
from datetime import datetime

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# app.main reads these at import; real values come from backend/.env when present.
for _key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "SESSION_SECRET"):
    os.environ.setdefault(_key, "test")
os.environ.setdefault("PUBLIC_BASE_URL", "http://localhost:5173")

from app.main import app  # noqa: E402
from app.models.user import User, UserCreate  # noqa: E402
from app.services import event_service, fight_service, user_service  # noqa: E402
from app.utils import db  # noqa: E402
from app.utils.auth import current_user, safe_next  # noqa: E402


@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    User.__table__.create(bind=engine)

    def fake_run_db_query(fn):
        with SessionLocal() as session:
            return fn(session)

    monkeypatch.setattr(user_service, "run_db_query", fake_run_db_query)
    return SessionLocal


@pytest.fixture
def client():
    # No `with`: the lifespan (pid reconcile, pg LISTEN) never runs.
    yield TestClient(app)
    app.dependency_overrides.clear()


def _as(role: str, user_id: int = 1, email: str = "someone@example.com") -> None:
    app.dependency_overrides[current_user] = lambda: User(
        id=user_id, email=email, role=role, is_active=True,
    )


# --- sign-in -----------------------------------------------------------------

def test_sign_in_creates_a_viewer(session_factory, monkeypatch):
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    user = user_service.sign_in("New.Person@Example.com", "New Person")
    assert user.email == "new.person@example.com"
    assert user.role == "viewer"
    assert user.is_active is True
    assert user.last_login_at is not None


def test_sign_in_bootstraps_admin_emails(session_factory, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com, other@example.com")
    assert user_service.sign_in("Boss@example.com", None).role == "admin"


def test_admin_emails_only_apply_on_creation(session_factory, monkeypatch):
    monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    user_service.sign_in("late@example.com", None)
    monkeypatch.setenv("ADMIN_EMAILS", "late@example.com")
    assert user_service.sign_in("late@example.com", None).role == "viewer"


def test_pre_provisioned_user_keeps_role_and_gets_name(session_factory):
    user_service.create_user(UserCreate(email="Labeller@Example.com", role="labeller"))
    user = user_service.sign_in("labeller@example.com", "Lab Eller")
    assert user.role == "labeller"
    assert user.name == "Lab Eller"
    assert len(user_service.list_users()) == 1


def test_create_user_rejects_duplicate_email(session_factory):
    user_service.create_user(UserCreate(email="dup@example.com"))
    with pytest.raises(user_service.EmailTaken):
        user_service.create_user(UserCreate(email="DUP@example.com"))


# --- post-login redirect -------------------------------------------------------

@pytest.mark.parametrize("path", ["/fights/12", "/training-data/jab?x=1", "/"])
def test_safe_next_keeps_same_origin_paths(path):
    assert safe_next(path) == path


@pytest.mark.parametrize("path", [
    None, "", "//evil.com", "https://evil.com", "/\\evil.com", "/\t/evil.com", "evil.com",
])
def test_safe_next_rejects_other_origins(path):
    assert safe_next(path) == "/"


# --- route protection ----------------------------------------------------------

def _dependency_calls(dependant):
    for dep in dependant.dependencies:
        yield dep.call
        yield from _dependency_calls(dep)


def test_every_api_route_requires_a_session():
    api_routes = [r for r in app.routes if isinstance(r, APIRoute) and r.path.startswith("/api/")]
    assert api_routes
    unprotected = [
        f"{sorted(r.methods)} {r.path}"
        for r in api_routes
        if not r.path.startswith("/api/auth/") and current_user not in _dependency_calls(r.dependant)
    ]
    assert unprotected == []


def test_no_session_is_401(client):
    assert client.get("/api/fights/").status_code == 401
    assert client.get("/api/auth/me").status_code == 401


_EVENT = {"kind": "point", "frame": 10, "corner": 0, "action": "jab"}


@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/fights/1/events/", _EVENT),
    ("put", "/api/fights/1/events/1", {"frame": 5}),
    ("put", "/api/fights/1/events/1/verify", {"is_verified": True}),
    ("put", "/api/fights/1/events/1/reclassify", {"action": "cross", "target": "head", "success": True}),
    ("delete", "/api/fights/1/events/1", None),
    ("post", "/api/fights/1/finish-labeling", None),
    ("post", "/api/fights/1/reopen-labeling", None),
])
def test_viewer_cannot_label(client, method, path, body):
    _as("viewer")
    kwargs = {"json": body} if body is not None else {}
    assert getattr(client, method)(path, **kwargs).status_code == 403


@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/fights/upload", None),
    ("delete", "/api/fights/1", None),
    ("post", "/api/fighters/", {"first_name": "A", "last_name": "B"}),
    ("post", "/api/eval-runs/", {"reference_fight_id": 1, "scored_fight_id": 2}),
    ("post", "/api/tracking/video", None),
    ("get", "/api/users/", None),
    ("post", "/api/users/", {"email": "x@example.com"}),
    ("patch", "/api/users/2", {"role": "admin"}),
])
def test_labeller_cannot_administer(client, method, path, body):
    _as("labeller")
    kwargs = {"json": body} if body is not None else {}
    assert getattr(client, method)(path, **kwargs).status_code == 403


def test_admin_cannot_edit_themselves(client):
    _as("admin", user_id=7)
    assert client.patch("/api/users/7", json={"role": "viewer"}).status_code == 409


def test_created_event_is_stamped_with_the_signed_in_labeller(client, monkeypatch):
    _as("labeller", email="lab@example.com")
    monkeypatch.setattr(fight_service, "get_fight_by_id", lambda fight_id: object())
    captured = {}

    def fake_create_event(fight_id, payload, labeler=None):
        captured["labeler"] = labeler
        return {
            "id": 1, "fight_id": fight_id, "source": "label", "kind": payload.kind,
            "frame": payload.frame, "end_frame": None, "description": None, "fighter_id": None,
            "corner": payload.corner, "action": payload.action, "target": None, "success": None,
            "state": None, "value": None, "labeler": labeler, "created_at": datetime(2026, 1, 1),
            "is_verified": None,
        }

    monkeypatch.setattr(event_service, "create_event", fake_create_event)
    response = client.post("/api/fights/1/events/", json={**_EVENT, "labeler": "spoofed"})
    assert response.status_code == 201
    assert captured["labeler"] == "lab@example.com"
