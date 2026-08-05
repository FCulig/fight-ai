from datetime import datetime
from typing import Optional

from sqlalchemy import Column, ForeignKey, Integer, String, TIMESTAMP, text
from pydantic import BaseModel, ConfigDict

from app.utils.db import Base


class Fight(Base):
    __tablename__ = "fights"

    id = Column(Integer, primary_key=True, index=True)
    video_path = Column(String(500), nullable=False, unique=True)
    fps = Column(Integer, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=text("now()"))
    state = Column(String(32), nullable=False, server_default=text("'queued'"))
    red_fighter_id = Column(Integer, ForeignKey("fighters.id", ondelete="SET NULL"), nullable=True)
    blue_fighter_id = Column(Integer, ForeignKey("fighters.id", ondelete="SET NULL"), nullable=True)


class FightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_path: str
    fps: int
    width: int
    height: int
    created_at: datetime
    state: str
    red_fighter_id: Optional[int]
    blue_fighter_id: Optional[int]
    red_fighter_name: Optional[str] = None
    blue_fighter_name: Optional[str] = None
