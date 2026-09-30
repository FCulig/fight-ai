import os
from dataclasses import dataclass
from functools import cache
from typing import Callable, Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request

from app.models.user import ROLE_RANK, User
from app.services import user_service

load_dotenv()

SESSION_COOKIE = "fightai_session"
SESSION_MAX_AGE = 14 * 24 * 60 * 60  # sliding: Starlette re-sets the cookie on every response

_REQUIRED_ENV = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "SESSION_SECRET", "PUBLIC_BASE_URL")


@dataclass(frozen=True)
class AuthConfig:
    google_client_id: str
    google_client_secret: str
    session_secret: str
    # The origin the browser sees (the Vite dev server in dev). The OAuth
    # redirect URI is built from it rather than from the request, because the
    # Vite proxy rewrites Host to 127.0.0.1:8000.
    public_base_url: str

    @property
    def callback_url(self) -> str:
        return f"{self.public_base_url}/api/auth/callback"

    @property
    def https_only(self) -> bool:
        return self.public_base_url.startswith("https://")


@cache
def get_config() -> AuthConfig:
    missing = [k for k in _REQUIRED_ENV if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Auth environment variables not set: {', '.join(missing)}")
    return AuthConfig(
        google_client_id=os.environ["GOOGLE_CLIENT_ID"],
        google_client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        session_secret=os.environ["SESSION_SECRET"],
        public_base_url=os.environ["PUBLIC_BASE_URL"].rstrip("/"),
    )


def current_user(request: Request) -> User:
    """Every API route except /api/auth/* depends on this (see app/main.py).
    The cookie holds only the user id; the row is re-read on every request so
    a role change or disable on the Users page applies immediately."""
    uid = request.session.get("uid")
    user = user_service.get_by_id(uid) if uid is not None else None
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="Not signed in")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Your access has been disabled")
    return user


def require_role(min_role: str) -> Callable[..., User]:
    if min_role not in ROLE_RANK:
        raise ValueError(f"unknown role {min_role!r}")

    def _require(user: User = Depends(current_user)) -> User:
        if ROLE_RANK[user.role] < ROLE_RANK[min_role]:
            raise HTTPException(status_code=403, detail=f"This needs the {min_role} role")
        return user

    return _require


def safe_next(path: Optional[str]) -> str:
    """Only same-origin paths may be a post-login redirect target. Browsers
    strip tabs and newlines and treat `\\` as `/`, so `/\\t/evil.com` would
    otherwise become the protocol-relative `//evil.com`."""
    if (
        not path
        or not path.startswith("/")
        or path.startswith("//")
        or any(c == "\\" or ord(c) < 0x20 or ord(c) == 0x7F for c in path)
    ):
        return "/"
    return path
