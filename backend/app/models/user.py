from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, Integer, String, TIMESTAMP, text
from pydantic import BaseModel, ConfigDict, field_validator

from app.utils.db import Base

# Ordered lowest to highest: each role can do everything the ones before it can.
ROLES = ("viewer", "labeller", "admin")
ROLE_RANK = {role: rank for rank, role in enumerate(ROLES)}


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(320), nullable=False, unique=True)
    name = Column(String(200), nullable=True)
    role = Column(String(20), nullable=False, server_default="viewer")
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    last_login_at = Column(TIMESTAMP, nullable=True)


def _check_role(role: Optional[str]) -> Optional[str]:
    if role is not None and role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    return role


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]


def _normalise_email(v: str) -> str:
    v = v.strip().lower()
    if "@" not in v or len(v) > 320:
        raise ValueError("email must be an email address")
    return v


class UserCreate(BaseModel):
    """Invites an email: sign-in is refused for any address without a row."""

    email: str
    role: str = "viewer"

    _email = field_validator("email")(_normalise_email)
    _role = field_validator("role")(_check_role)


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None

    _role = field_validator("role")(_check_role)


class WaitlistEntry(Base):
    """An address that asked to hear when the product opens to everyone."""

    __tablename__ = "waitlist"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(320), nullable=False, unique=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class WaitlistJoin(BaseModel):
    email: str

    _email = field_validator("email")(_normalise_email)


class WaitlistEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime
