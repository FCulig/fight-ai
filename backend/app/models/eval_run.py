from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, Float, ForeignKey, Integer, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import BaseModel, ConfigDict

from app.utils.db import Base


class EvalRun(Base):
    """One `python -m eval.cli score-pair` run: `reference_fight_id`'s hand
    labels scored against `scored_fight_id`'s pipeline predictions — two
    different fights, per the real accuracy workflow (see backend/CLAUDE.md,
    "Pipeline accuracy is validated by..."). `report` is the exact `report`
    sub-object `ai/eval/report_io.save_report()` already produces; see
    db/alembic/versions/b4ea83f7c87b_create_eval_runs_table.py for why it
    isn't normalised into columns."""

    __tablename__ = "eval_runs"

    id = Column(Integer, primary_key=True, index=True)
    reference_fight_id = Column(Integer, ForeignKey("fights.id", ondelete="CASCADE"), nullable=False)
    scored_fight_id = Column(Integer, ForeignKey("fights.id", ondelete="CASCADE"), nullable=False)
    git_sha = Column(String(40), nullable=False)
    constants_sha256 = Column(String(64), nullable=False)
    tolerance_secs = Column(Float, nullable=False)
    tolerance_frames = Column(Integer, nullable=False)
    scored_minutes = Column(Float, nullable=False)
    report = Column(JSONB, nullable=False)
    generated_at = Column(TIMESTAMP, nullable=False, server_default=text("now()"))
    triggered_by = Column(String(200), nullable=True)


class EvalRunSummary(BaseModel):
    """List-endpoint shape — omits the full `report` blob (it can be large:
    per-strike miss/spurious lists, confusion matrices, ...). The fixture
    table (E2) and version-trend chart (E8) only need the headline numbers.

    `f1`/`precision`/`recall`/`tp`/`fp`/`fn` are stamped onto the ORM row by
    `eval_run_service._summarize()` — the stored `report` blob only has
    tp/fp/fn (`dataclasses.asdict()` doesn't serialise `PRF`'s
    precision/recall/f1 *properties*, same as every other score.py
    dataclass), so they're computed once at read time rather than duplicated
    into the stored JSON.

    `pipeline_version` is stamped the same way — `scored_fight_id`'s 1-based
    rank among this fixture's scored fights (see
    `eval_run_service._pipeline_versions`)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_fight_id: int
    scored_fight_id: int
    pipeline_version: int
    git_sha: str
    constants_sha256: str
    tolerance_secs: float
    tolerance_frames: int
    scored_minutes: float
    generated_at: datetime
    triggered_by: Optional[str] = None
    f1: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    tp: Optional[int] = None
    fp: Optional[int] = None
    fn: Optional[int] = None
    offset_bias_frames: Optional[float] = None
    offset_jitter_frames: Optional[float] = None


class EvalRunResponse(EvalRunSummary):
    """Single-run shape — includes the full nested report for the E3–E9
    drill-down (classification, confusion, timing, rounds, worst misses)."""

    report: dict[str, Any]


class EvalRunCreate(BaseModel):
    reference_fight_id: int
    scored_fight_id: int
    tolerance_secs: Optional[float] = None


class FixtureSummary(BaseModel):
    """One row of `GET /eval-runs/fixtures` — every `purpose='reference'`,
    labelled fight, with its latest run or `is_measurable=False` (Section E's
    "E0 — not measurable yet" state) when it has none."""

    reference_fight_id: int
    video_path: str
    labeled_at: datetime
    is_measurable: bool
    latest_run: Optional[EvalRunSummary] = None
