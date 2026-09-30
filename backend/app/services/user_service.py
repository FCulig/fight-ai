import os
from typing import List, Optional

from sqlalchemy import func

from app.models.user import User, UserCreate, UserUpdate
from app.utils.db import run_db_query


class EmailTaken(Exception):
    pass


def _admin_emails() -> set[str]:
    """`ADMIN_EMAILS` bootstraps the first admin: an address listed here is
    created as admin on its first sign-in. It is read only at creation, so an
    admin demoted later on the Users page stays demoted."""
    raw = os.getenv("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def get_by_id(user_id: int) -> Optional[User]:
    def _query(session):
        return session.query(User).filter(User.id == user_id).first()

    return run_db_query(_query)


def sign_in(email: str, name: Optional[str]) -> User:
    """Get-or-create the user for a verified Google email and stamp the login.
    New addresses join as viewers (or admin via `ADMIN_EMAILS`). A row an
    admin pre-provisioned keeps its role and picks up the Google name. The
    caller decides what to do with an inactive user."""
    email = email.strip().lower()

    def _query(session):
        user = session.query(User).filter(User.email == email).first()
        if user is None:
            role = "admin" if email in _admin_emails() else "viewer"
            user = User(email=email, name=name, role=role)
            session.add(user)
        elif name and not user.name:
            user.name = name
        user.last_login_at = func.now()
        session.commit()
        session.refresh(user)
        return user

    return run_db_query(_query)


def list_users() -> List[User]:
    def _query(session):
        return session.query(User).order_by(User.email).all()

    return run_db_query(_query)


def create_user(payload: UserCreate) -> User:
    def _query(session):
        if session.query(User).filter(User.email == payload.email).first() is not None:
            raise EmailTaken(f"{payload.email} already has an account")
        user = User(email=payload.email, role=payload.role)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    return run_db_query(_query)


def update_user(user_id: int, payload: UserUpdate) -> Optional[User]:
    def _query(session):
        user = session.query(User).filter(User.id == user_id).first()
        if user is None:
            return None
        if payload.role is not None:
            user.role = payload.role
        if payload.is_active is not None:
            user.is_active = payload.is_active
        session.commit()
        session.refresh(user)
        return user

    return run_db_query(_query)
