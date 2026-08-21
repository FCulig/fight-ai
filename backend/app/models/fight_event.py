from typing import Optional

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from pydantic import BaseModel, ConfigDict

from app.utils.db import Base


class FightEvent(Base):
    __tablename__ = "fight_events"

    id = Column(Integer, primary_key=True, index=True)
    frame = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    fight_id = Column(Integer, ForeignKey("fights.id", ondelete="CASCADE"), nullable=False)
    fighter_id = Column(Integer, ForeignKey("fighters.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(50), nullable=True)
    success = Column(Boolean, nullable=True)
    state = Column(String(20), nullable=True)


class FightEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    frame: int
    description: str
    fight_id: int
    fighter_id: Optional[int]
    action: Optional[str]
    success: Optional[bool]
    state: Optional[str]
