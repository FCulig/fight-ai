import json
import os

import psycopg2
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

# The pipeline worker reaches Postgres through an SSH tunnel from a laptop that
# sleeps (deploy/worker.sh), so pre-ping and TCP keepalives replace dead pooled
# connections instead of failing on them. values_plus_batch sends the text()
# bulk inserts in fight_processing 1000 rows per round trip; psycopg2's default
# is one round trip per row, about 50 minutes for a long fight at 36 ms.
engine = create_engine(
    os.getenv("DATABASE_URL"),
    pool_pre_ping=True,
    executemany_mode="values_plus_batch",
    executemany_batch_page_size=1000,
    connect_args={"keepalives": 1, "keepalives_idle": 30, "keepalives_interval": 10, "keepalives_count": 3},
)
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


# ---------------------------------------------------------------------------
# Pipeline worker (pipeline.run_worker, started by deploy/worker.sh)
# ---------------------------------------------------------------------------

# Held by the worker for its whole run, so only one worker drains the queue.
# The backend reads the same key from pg_locks to tell whether a worker is
# online (backend/app/services/notification_service.py): keep the two in step.
WORKER_LOCK_KEY = 7274030

# The states a fight passes through while the pipeline runs on it.
_PIPELINE_STATES = ("detecting", "tracking", "pose", "corners", "scoreboard", "segmenting", "analyzing")


def _notify(db, fight_id: int, state: str) -> None:
    db.execute(
        text("SELECT pg_notify('fight_state', :payload)"),
        {"payload": json.dumps({"id": fight_id, "state": state})},
    )


def claim_next_queued_fight():
    """Move the oldest `queued` fight to `detecting` and return its
    (id, video_path, purpose), or None when the queue is empty. SKIP LOCKED
    makes the claim atomic, so two workers can never take the same fight."""
    db = SessionLocal()
    try:
        row = db.execute(text(
            "UPDATE fights SET state = 'detecting' WHERE id = ("
            " SELECT id FROM fights WHERE state = 'queued' ORDER BY id"
            " FOR UPDATE SKIP LOCKED LIMIT 1"
            ") RETURNING id, video_path, purpose"
        )).fetchone()
        if row is not None:
            _notify(db, row.id, "detecting")
        db.commit()
        return row
    finally:
        db.close()


def requeue_abandoned_fights() -> list[int]:
    """Put fights left mid-pipeline back in the queue: the laptop slept, the
    network dropped, or the worker was stopped. Call it only while holding the
    worker lock, because then no other worker can be processing them. A local
    pipeline started by the upload validator records its pid, so `pid IS NULL`
    leaves that one alone."""
    db = SessionLocal()
    try:
        ids = [row.id for row in db.execute(
            text(
                "UPDATE fights SET state = 'queued' "
                "WHERE state IN :states AND pid IS NULL RETURNING id"
            ).bindparams(bindparam("states", expanding=True)),
            {"states": list(_PIPELINE_STATES)},
        )]
        for fight_id in ids:
            _notify(db, fight_id, "queued")
        db.commit()
        return ids
    finally:
        db.close()


class WorkerLock:
    """The worker's advisory lock, on a connection of its own, because a
    session-level lock lasts exactly as long as its connection. When the laptop
    sleeps, the tunnel drops and the server releases the lock about 90 s later
    (sshd's ClientAlive setting, deploy/bootstrap-server.sh). `ensure()` then
    re-acquires it on a new connection."""

    def __init__(self) -> None:
        self._conn = None

    def acquire(self) -> bool:
        self.release()
        conn = psycopg2.connect(
            os.getenv("DATABASE_URL"),
            keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (WORKER_LOCK_KEY,))
            held = cur.fetchone()[0]
        if held:
            self._conn = conn
        else:
            conn.close()
        return held

    def ensure(self) -> bool:
        """True while this worker holds the lock, reconnecting first if needed."""
        if self._conn is not None:
            try:
                with self._conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return True
            except psycopg2.Error:
                self.release()
        return self.acquire()

    def release(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except psycopg2.Error:
                pass
            self._conn = None
