"""Emails sent when a fight changes state.

`fight_state_listener` hands every `fight_state` notification to `submit()`.
The work runs on a background thread, so a slow SMTP server never holds up the
SSE stream. The rules:

- `queued`: tell every active admin that uploads are waiting for the pipeline
  worker, unless a worker is online and will take them anyway. A running worker
  holds ai/database.py's WORKER_LOCK_KEY advisory lock.
- `completed`, or `labeling_in_progress` for the first time: tell the uploader
  the fight is ready. Reopening a finished labelling fight also lands in
  `labeling_in_progress`, but by then `labeled_at` is set.
- `failed` or `invalid`: tell the uploader it didn't work.

Dev-login accounts (`@fightai.local`) are never emailed.
"""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlalchemy import text

from app.services import email_service
from app.services.user_service import DEV_EMAIL_DOMAIN
from app.utils.auth import get_config
from app.utils.db import run_db_query

# Must match WORKER_LOCK_KEY in ai/database.py.
WORKER_LOCK_KEY = 7274030

_NOTIFYING_STATES = ("queued", "completed", "labeling_in_progress", "failed", "invalid")

log = logging.getLogger("uvicorn.error")
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="notify")


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str


@dataclass(frozen=True)
class FightFacts:
    id: int
    title: str
    purpose: str
    labeled_at_set: bool
    uploader_email: Optional[str]
    reported_frames: Optional[int] = None
    decoded_frames: Optional[int] = None


def submit(payload: str) -> None:
    """Called from the listener thread for every state change."""
    _executor.submit(_handle, payload)


def _handle(payload: str) -> None:
    try:
        event = json.loads(payload)
        emails = _emails_for(event["id"], event["state"])
    except Exception:
        log.exception("Couldn't work out notifications for %s", payload)
        return
    for email in emails:
        try:
            email_service.send(email.to, email.subject, email.body)
        except Exception:
            log.exception("Couldn't email %s about %s", email.to, payload)


def _emails_for(fight_id: int, state: str) -> list[Email]:
    if state not in _NOTIFYING_STATES:
        return []
    if state == "queued":
        if _worker_online():
            return []
        return queued_emails(_admin_emails(), _queued_titles(), _base_url())
    fight = _load_fight(fight_id)
    if fight is None:
        return []
    return uploader_emails(state, fight, _base_url())


# ---- what to send ---------------------------------------------------------------

def queued_emails(admins: list[str], queue: list[str], base_url: str) -> list[Email]:
    if not admins or not queue:
        return []
    count = f"{len(queue)} video{'s' if len(queue) != 1 else ''}"
    listing = "\n".join(f"  - {title}" for title in queue)
    body = (
        "These uploads passed validation and are waiting for the pipeline worker:\n\n"
        f"{listing}\n\n"
        "Start the worker on your laptop to process them:\n\n"
        "  deploy/worker.sh\n\n"
        f"Fightlytics: {base_url}\n"
    )
    return [Email(admin, f"Fightlytics: {count} waiting for processing", body) for admin in admins]


def uploader_emails(state: str, fight: FightFacts, base_url: str) -> list[Email]:
    to = fight.uploader_email
    if not to:
        return []
    if state == "completed":
        return [Email(
            to, f"Fightlytics: {fight.title} is ready",
            f"{fight.title} has been processed. Its AI annotations are ready to review:\n\n"
            f"{base_url}/fights/{fight.id}\n",
        )]
    if state == "labeling_in_progress" and not fight.labeled_at_set:
        return [Email(
            to, f"Fightlytics: {fight.title} is ready to label",
            f"{fight.title} has been processed. Fighter tracking is done, so it's ready to label:\n\n"
            f"{base_url}/fights/{fight.id}/annotate\n",
        )]
    if state == "failed":
        return [Email(
            to, f"Fightlytics: processing failed for {fight.title}",
            f"The pipeline failed while processing {fight.title}. You can delete it and "
            f"upload it again from the fight list:\n\n{base_url}/\n",
        )]
    if state == "invalid":
        frames = ""
        if fight.reported_frames and fight.decoded_frames is not None:
            frames = f" Only {fight.decoded_frames} of its {fight.reported_frames} frames could be decoded."
        return [Email(
            to, f"Fightlytics: {fight.title} could not be processed",
            f"{fight.title} didn't pass validation, so it wasn't processed.{frames} The file is "
            f"probably truncated: download or export it again, then upload it again:\n\n{base_url}/\n",
        )]
    return []


def _title(video_path: str, red: Optional[str], blue: Optional[str]) -> str:
    if red and blue:
        return f"{red} vs {blue}"
    return Path(video_path).stem


def _real_addresses(emails) -> list[str]:
    return [e for e in emails if e and not e.endswith(f"@{DEV_EMAIL_DOMAIN}")]


# ---- what the database says -------------------------------------------------------

def _base_url() -> str:
    return get_config().public_base_url


def _worker_online() -> bool:
    def _query(session):
        return session.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' "
                "AND classid = 0 AND objid = CAST(:key AS oid) AND objsubid = 1 AND granted)"
            ),
            {"key": WORKER_LOCK_KEY},
        ).scalar()

    return bool(run_db_query(_query))


def _admin_emails() -> list[str]:
    def _query(session):
        rows = session.execute(
            text("SELECT email FROM users WHERE role = 'admin' AND is_active ORDER BY email")
        ).fetchall()
        return [row.email for row in rows]

    return _real_addresses(run_db_query(_query))


_FIGHTER_JOINS = (
    "LEFT JOIN fighters r ON r.id = f.red_fighter_id "
    "LEFT JOIN fighters b ON b.id = f.blue_fighter_id "
)
_FIGHTER_NAMES = (
    "r.first_name || ' ' || r.last_name AS red_name, "
    "b.first_name || ' ' || b.last_name AS blue_name"
)


def _queued_titles() -> list[str]:
    def _query(session):
        return session.execute(text(
            f"SELECT f.video_path, {_FIGHTER_NAMES} FROM fights f {_FIGHTER_JOINS}"
            "WHERE f.state = 'queued' ORDER BY f.id"
        )).fetchall()

    return [_title(row.video_path, row.red_name, row.blue_name) for row in run_db_query(_query)]


def _load_fight(fight_id: int) -> Optional[FightFacts]:
    def _query(session):
        return session.execute(text(
            "SELECT f.id, f.video_path, f.purpose, f.labeled_at IS NOT NULL AS labeled, "
            "f.reported_frames, f.decoded_frames, u.email AS uploader_email, "
            f"u.is_active AS uploader_active, {_FIGHTER_NAMES} "
            f"FROM fights f LEFT JOIN users u ON u.id = f.uploaded_by {_FIGHTER_JOINS}"
            "WHERE f.id = :id"
        ), {"id": fight_id}).fetchone()

    row = run_db_query(_query)
    if row is None:
        return None
    uploader = None
    if row.uploader_email and row.uploader_active:
        uploader = next(iter(_real_addresses([row.uploader_email])), None)
    return FightFacts(
        id=row.id,
        title=_title(row.video_path, row.red_name, row.blue_name),
        purpose=row.purpose,
        labeled_at_set=row.labeled,
        uploader_email=uploader,
        reported_frames=row.reported_frames,
        decoded_frames=row.decoded_frames,
    )
