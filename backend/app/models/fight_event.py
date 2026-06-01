from typing import Optional

from sqlalchemy import Column, ForeignKey, Integer, Text
from pydantic import BaseModel, ConfigDict

from app.utils.db import Base


class FightEvent(Base):
    __tablename__ = "fight_events"

    id = Column(Integer, primary_key=True, index=True)
    frame = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    fight_id = Column(Integer, ForeignKey("fights.id", ondelete="CASCADE"), nullable=True)


class FightEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    frame: int
    description: str
    fight_id: Optional[int]
