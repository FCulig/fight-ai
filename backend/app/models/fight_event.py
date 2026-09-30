from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, TIMESTAMP, text
from pydantic import BaseModel, ConfigDict, model_validator

from app.utils.db import Base

EVENT_KINDS = ("point", "round", "corner_swap", "excluded")


class FightEvent(Base):
    __tablename__ = "fight_events"

    id = Column(Integer, primary_key=True, index=True)
    fight_id = Column(Integer, ForeignKey("fights.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(20), nullable=False)
    kind = Column(String(20), nullable=False)
    frame = Column(Integer, nullable=False)
    end_frame = Column(Integer, nullable=True)
    description = Column(Text, nullable=True)
    fighter_id = Column(Integer, ForeignKey("fighters.id", ondelete="SET NULL"), nullable=True)
    corner = Column(Integer, nullable=True)
    action = Column(String(50), nullable=True)
    target = Column(String(10), nullable=True)
    success = Column(Boolean, nullable=True)
    state = Column(String(20), nullable=True)
    value = Column(String(200), nullable=True)
    labeler = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    is_verified = Column(Boolean, nullable=True)


class FightEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fight_id: int
    source: str
    kind: str
    frame: int
    end_frame: Optional[int]
    description: Optional[str]
    fighter_id: Optional[int]
    corner: Optional[int]
    action: Optional[str]
    target: Optional[str]
    success: Optional[bool]
    state: Optional[str]
    value: Optional[str]
    labeler: Optional[str]
    created_at: datetime
    is_verified: Optional[bool]


class FightEventCreate(BaseModel):
    """The Annotate frontend's only write shape. `source` is deliberately not
    a field here — the service always writes `source="label"`, since this is
    exclusively Annotate's write path (the AI pipeline writes predictions via
    its own raw SQL, never through this schema). That makes it structurally
    impossible for a client request to spoof a prediction row. `labeler` is
    left out for the same reason: the route stamps the signed-in user's email."""

    kind: str = "point"
    frame: int
    end_frame: Optional[int] = None
    description: Optional[str] = None
    corner: Optional[int] = None
    action: Optional[str] = None
    target: Optional[str] = None
    success: Optional[bool] = None
    value: Optional[str] = None

    @model_validator(mode="after")
    def _validate_shape(self) -> "FightEventCreate":
        if self.kind not in EVENT_KINDS:
            raise ValueError(f"kind must be one of {EVENT_KINDS}")
        # fight_end is the one action with no structured way to reconstruct
        # its text (winner/method/detail aren't columns) — everything else is
        # rebuilt on demand client-side from action/target/corner, so storing
        # it would just go stale the next time a corner_swap span is edited.
        if self.kind == "point" and self.action == "fight_end" and not self.description:
            raise ValueError("description is required for a fight_end event")
        if self.corner is not None and self.corner not in (0, 1):
            raise ValueError("corner must be 0 (red) or 1 (blue)")
        if self.action and self.action.startswith("state_") and self.corner is not None:
            raise ValueError("corner must be null for a state_* action — a fight state isn't scoped to a corner")
        return self


class FightEventUpdate(BaseModel):
    """Range (round/corner_swap/excluded) edits only — point events are
    create+delete-only, same as label_events always was."""

    frame: Optional[int] = None
    end_frame: Optional[int] = None
    value: Optional[str] = None


class FightEventVerify(BaseModel):
    """Training Data QA's only write shape. `is_verified` is a tri-state:
    True (confirmed training-worthy), False (declined), or None (back to
    pending) — always required in the payload so "clear the verdict" is a
    real, explicit request rather than an omitted field."""

    is_verified: Optional[bool]


class FightEventReclassify(BaseModel):
    """Training Data QA's strike-retyping write path — lets a reviewer fix a
    mislabelled action (e.g. a jab that's really a cross) without a full
    create+delete re-label. `target`/`success` are computed client-side from
    `newAction` (via trainingDataTaxonomy.ts's reclassifyPayload(), mirroring
    what Annotate's own palette derives for a fresh label of the same
    action) and sent explicitly rather than re-derived here, same division
    of labour as the rest of the app: the backend stores columns, taxonomy
    lives in the frontend."""

    action: str
    target: Optional[str] = None
    success: Optional[bool] = None
