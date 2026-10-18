import os
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.models.user import User, UserCreate, UserUpdate, WaitlistEntry
from app.utils.db import run_db_query


# Not a real TLD's domain, so no Google account can ever sign in as one of these.
DEV_EMAIL_DOMAIN = "fightai.local"


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


def sign_in(email: str, name: Optional[str]) -> Optional[User]:
    """Stamp the login for a verified Google email and return its user.
    Sign-in is invite-only: an address without a row gets None, unless it is
    in `ADMIN_EMAILS`, which creates it as admin. An invited row keeps its
    role and picks up the Google name. The caller decides what to do with an
    inactive user."""
    email = email.strip().lower()

    def _query(session):
        user = session.query(User).filter(User.email == email).first()
        if user is None:
            if email not in _admin_emails():
                return None
            user = User(email=email, name=name, role="admin")
            session.add(user)
        elif name and not user.name:
            user.name = name
        user.last_login_at = func.now()
        session.commit()
        session.refresh(user)
        return user

    return run_db_query(_query)


def dev_sign_in(role: str) -> User:
    """Get-or-create the synthetic user for `role` (DEV_LOGIN only). The role
    and active flag are reset on every call, so an edit on the Users page
    can't leave `dev-admin` unable to administer."""
    email = f"dev-{role}@{DEV_EMAIL_DOMAIN}"

    def _query(session):
        user = session.query(User).filter(User.email == email).first()
        if user is None:
            user = User(email=email, name=f"Dev {role}")
            session.add(user)
        user.role = role
        user.is_active = True
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
        # An invited address no longer needs the "we're open" email.
        session.query(WaitlistEntry).filter(WaitlistEntry.email == payload.email).delete()
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


def join_waitlist(email: str) -> None:
    """Idempotent, and silent about whether the address was already listed or
    already has an account, because anyone can call it."""

    def _query(session):
        if session.query(User).filter(User.email == email).first() is not None:
            return
        if session.query(WaitlistEntry).filter(WaitlistEntry.email == email).first() is None:
            session.add(WaitlistEntry(email=email))
            try:
                session.commit()
            except IntegrityError:  # a concurrent join of the same address
                session.rollback()

    run_db_query(_query)


def list_waitlist() -> List[WaitlistEntry]:
    def _query(session):
        return session.query(WaitlistEntry).order_by(WaitlistEntry.created_at).all()

    return run_db_query(_query)
