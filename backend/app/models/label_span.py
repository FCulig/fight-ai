from datetime import datetime
from typing import Optional

from sqlalchemy import Column, ForeignKey, Integer, String, TIMESTAMP, text
from pydantic import BaseModel, ConfigDict

from app.utils.db import Base

SPAN_KINDS = ("round", "corner_swap", "excluded")


class LabelSpan(Base):
    __tablename__ = "label_spans"

    id = Column(Integer, primary_key=True, index=True)
    fight_id = Column(Integer, ForeignKey("fights.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(20), nullable=False)
    start_frame = Column(Integer, nullable=False)
    end_frame = Column(Integer, nullable=True)
    value = Column(String(200), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=text("now()"))


class LabelSpanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fight_id: int
    kind: str
    start_frame: int
    end_frame: Optional[int]
    value: Optional[str]
    created_at: datetime


class LabelSpanCreate(BaseModel):
    kind: str
    start_frame: int
    end_frame: Optional[int] = None
    value: Optional[str] = None


class LabelSpanUpdate(BaseModel):
    start_frame: Optional[int] = None
    end_frame: Optional[int] = None
    value: Optional[str] = None
