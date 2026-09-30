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


class UserCreate(BaseModel):
    """Pre-provisions an email before its first sign-in, so the person lands
    with the right role instead of as a viewer."""

    email: str
    role: str = "viewer"

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v:
            raise ValueError("email must be an email address")
        return v

    _role = field_validator("role")(_check_role)


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None

    _role = field_validator("role")(_check_role)
