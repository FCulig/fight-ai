import json
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))
SessionLocal = sessionmaker(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def set_fight_state(fight_id: int, state) -> None:
    state_val = state.value if hasattr(state, "value") else state
    db = SessionLocal()
    try:
        db.execute(
            text("UPDATE fights SET state = :state WHERE id = :id"),
            {"state": state_val, "id": fight_id},
        )
        db.execute(
            text("SELECT pg_notify('fight_state', :payload)"),
            {"payload": json.dumps({"id": fight_id, "state": state_val})},
        )
        db.commit()
    finally:
        db.close()


def set_video_check(fight_id: int, reported_frames: int, decoded_frames: int) -> None:
    """Persist the full-decode validation result (see eval/videocheck.py) so an
    INVALID fight can show why it was rejected instead of a bare badge."""
    db = SessionLocal()
    try:
        db.execute(
            text(
                "UPDATE fights SET reported_frames = :r, decoded_frames = :d "
                "WHERE id = :id"
            ),
            {"r": reported_frames, "d": decoded_frames, "id": fight_id},
        )
        db.commit()
    finally:
        db.close()


def set_segmentation_review(
    fight_id: int, needs_review: bool, reason: str | None
) -> None:
    """Persist segmentation's own verdict on whether its round list should be
    confirmed by a human before it is trusted.

    Round segmentation fails silently: when scoreboard OCR is unavailable the
    round count falls back to fighter-detection heuristics, which split a round
    on any long camera cutaway, and the result lands in `rounds` looking exactly
    like a clock-verified one. This is what lets the annotation UI say so."""
    db = SessionLocal()
    try:
        db.execute(
            text(
                "UPDATE fights SET segmentation_needs_review = :needs, "
                "segmentation_review_reason = :reason WHERE id = :id"
            ),
            {"needs": needs_review, "reason": reason or None, "id": fight_id},
        )
        db.commit()
    finally:
        db.close()


def set_fight_pid(fight_id: int, pid: int | None) -> None:
    """Point `fights.pid` at whichever AI-venv process is currently running for
    this fight (validator, then pipeline), so DELETE /fights/{id} always kills
    the right one. See pipeline_runner.py's _AI_ENTRYPOINTS."""
    db = SessionLocal()
    try:
        db.execute(
            text("UPDATE fights SET pid = :pid WHERE id = :id"),
            {"pid": pid, "id": fight_id},
        )
        db.commit()
    finally:
        db.close()
