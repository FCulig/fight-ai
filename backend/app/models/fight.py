from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, TIMESTAMP, text
from pydantic import BaseModel, ConfigDict

from app.utils.db import Base


# What the video is for. Written once by POST /fights/upload and never again —
# in particular the AI pipeline never touches it, so a `reference` fight keeps
# its identity when it is re-run to produce predictions to score against.
FIGHT_PURPOSES = ("training_data", "reference", "ai_labeled")


class Fight(Base):
    __tablename__ = "fights"

    id = Column(Integer, primary_key=True, index=True)
    video_path = Column(String(500), nullable=False, unique=True)
    fps = Column(Integer, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False, server_default=text("now()"))
    state = Column(String(32), nullable=False, server_default=text("'queued'"))
    pid = Column(Integer, nullable=True)
    labeled_at = Column(TIMESTAMP, nullable=True)
    purpose = Column(String(32), nullable=False, server_default=text("'ai_labeled'"))
    reported_frames = Column(Integer, nullable=True)
    decoded_frames = Column(Integer, nullable=True)
    # Segmentation's own verdict on its round list — see ai/database.py
    # set_segmentation_review. Written by the pipeline, never by labelling.
    segmentation_needs_review = Column(
        Boolean, nullable=False, server_default=text("false")
    )
    segmentation_review_reason = Column(Text, nullable=True)
    red_fighter_id = Column(Integer, ForeignKey("fighters.id", ondelete="SET NULL"), nullable=True)
    blue_fighter_id = Column(Integer, ForeignKey("fighters.id", ondelete="SET NULL"), nullable=True)
    # Who uploaded it. Written once by POST /fights/upload; NULL for older fights
    # and ones the pipeline registered itself. Gets the "processing finished" email.
    uploaded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class FightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_path: str
    fps: int
    width: int
    height: int
    created_at: datetime
    state: str
    labeled_at: Optional[datetime]
    purpose: str
    reported_frames: Optional[int]
    decoded_frames: Optional[int]
    segmentation_needs_review: bool = False
    segmentation_review_reason: Optional[str] = None
    red_fighter_id: Optional[int]
    blue_fighter_id: Optional[int]
    red_fighter_name: Optional[str] = None
    blue_fighter_name: Optional[str] = None
    uploaded_by: Optional[int] = None
