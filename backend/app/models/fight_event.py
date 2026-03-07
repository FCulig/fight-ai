from sqlalchemy import Column, Integer, Text
from app.utils.db import Base
from pydantic import BaseModel, ConfigDict


class FightEvent(Base):
    __tablename__ = "fight_events"

    id = Column(Integer, primary_key=True, index=True)
    frame = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)


class FightEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    frame: int
    description: str
