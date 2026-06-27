from typing import List, Optional

from sqlalchemy import Column, Float, ForeignKey, Integer, JSON
from pydantic import BaseModel, ConfigDict

from app.utils.db import Base


class FighterFrame(Base):
    __tablename__ = "fighter_frames"

    id = Column(Integer, primary_key=True, index=True)
    fight_id = Column(Integer, ForeignKey("fights.id", ondelete="CASCADE"), nullable=False)
    frame = Column(Integer, nullable=False)
    corner = Column(Integer, nullable=False)
    x1 = Column(Float, nullable=False)
    y1 = Column(Float, nullable=False)
    x2 = Column(Float, nullable=False)
    y2 = Column(Float, nullable=False)
    confidence = Column(Float, nullable=True)
    keypoints = Column(JSON, nullable=True)


class FighterFrameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fight_id: int
    frame: int
    corner: int
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: Optional[float]
    keypoints: Optional[List[List[float]]] = None
