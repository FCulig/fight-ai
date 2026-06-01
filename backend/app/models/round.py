from sqlalchemy import Column, ForeignKey, Integer
from pydantic import BaseModel, ConfigDict

from app.utils.db import Base


class Round(Base):
    __tablename__ = "rounds"

    id = Column(Integer, primary_key=True, index=True)
    fight_id = Column(Integer, ForeignKey("fights.id", ondelete="CASCADE"), nullable=False)
    round_number = Column(Integer, nullable=False)
    start_frame = Column(Integer, nullable=False)
    end_frame = Column(Integer, nullable=False)


class RoundResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fight_id: int
    round_number: int
    start_frame: int
    end_frame: int
