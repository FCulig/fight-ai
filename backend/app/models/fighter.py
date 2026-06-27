from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, TIMESTAMP, text
from pydantic import BaseModel, ConfigDict

from app.utils.db import Base


class Fighter(Base):
    __tablename__ = "fighters"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    nickname = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=text("now()"))


class FighterCreate(BaseModel):
    first_name: str
    last_name: str
    nickname: Optional[str] = None


class FighterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    nickname: Optional[str]
    created_at: datetime
