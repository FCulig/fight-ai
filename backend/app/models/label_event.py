from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, TIMESTAMP, text
from pydantic import BaseModel, ConfigDict, model_validator

from app.utils.db import Base


class LabelEvent(Base):
    __tablename__ = "label_events"

    id = Column(Integer, primary_key=True, index=True)
    fight_id = Column(Integer, ForeignKey("fights.id", ondelete="CASCADE"), nullable=False)
    frame = Column(Integer, nullable=False)
    corner = Column(Integer, nullable=True)
    action = Column(String(50), nullable=True)
    target = Column(String(10), nullable=True)
    success = Column(Boolean, nullable=True)
    description = Column(Text, nullable=False)
    labeler = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=text("now()"))


class LabelEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    frame: int
    description: str
    fight_id: int
    corner: Optional[int]
    action: Optional[str]
    target: Optional[str]
    success: Optional[bool]
    labeler: Optional[str]
    created_at: datetime


class LabelEventCreate(BaseModel):
    frame: int
    description: str
    corner: Optional[int] = None
    action: Optional[str] = None
    target: Optional[str] = None
    success: Optional[bool] = None
    labeler: Optional[str] = None

    @model_validator(mode="after")
    def _state_marks_have_no_corner(self) -> "LabelEventCreate":
        """A fight-state mark (STRIKING/CLINCH/GROUND) is a property of the
        fight, not a fighter — nothing in the row shape stops a future
        palette item or a direct API call from attaching one anyway, so this
        is a schema-level guard rather than relying on the frontend always
        sending `corner: null` (see TODO.md #1)."""
        if self.action and self.action.startswith("state_") and self.corner is not None:
            raise ValueError("corner must be null for a state_* action — a fight state isn't scoped to a corner")
        return self
