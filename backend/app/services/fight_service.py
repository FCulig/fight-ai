from typing import List

from sqlalchemy import bindparam, text
from app.utils.db import run_db_query
from app.models.fight import Fight
from app.models.fighter import Fighter


def _attach_fighter_names(session, fights: list[Fight]) -> list[Fight]:
    fighter_ids = set()
    for f in fights:
        if f.red_fighter_id:
            fighter_ids.add(f.red_fighter_id)
        if f.blue_fighter_id:
            fighter_ids.add(f.blue_fighter_id)
    if not fighter_ids:
        return fights
    rows = session.query(Fighter.id, Fighter.first_name, Fighter.last_name).filter(
        Fighter.id.in_(fighter_ids)
    ).all()
    names = {r.id: f"{r.first_name} {r.last_name}" for r in rows}
    for f in fights:
        f.red_fighter_name = names.get(f.red_fighter_id)
        f.blue_fighter_name = names.get(f.blue_fighter_id)
    return fights


def get_all_fights() -> List[Fight]:
    def _query(session):
        fights = session.query(Fight).order_by(Fight.id).all()
        return _attach_fighter_names(session, fights)

    return run_db_query(_query)


def get_processed_fights() -> List[Fight]:
    def _query(session):
        fights = session.query(Fight).filter(Fight.state == "completed").order_by(Fight.id).all()
        return _attach_fighter_names(session, fights)

    return run_db_query(_query)


def get_fight_by_id(fight_id: int) -> Fight | None:
    def _query(session):
        fight = session.query(Fight).filter(Fight.id == fight_id).first()
        if fight:
            _attach_fighter_names(session, [fight])
        return fight

    return run_db_query(_query)


def create_fight(
    video_path: str,
    fps: int,
    width: int,
    height: int,
    red_fighter_id: int | None = None,
    blue_fighter_id: int | None = None,
) -> Fight:
    def _query(session):
        fight = Fight(
            video_path=video_path,
            fps=fps,
            width=width,
            height=height,
            red_fighter_id=red_fighter_id,
            blue_fighter_id=blue_fighter_id,
        )
        session.add(fight)
        session.flush()
        import json
        session.execute(
            text("SELECT pg_notify('fight_state', :payload)"),
            {"payload": json.dumps({"id": fight.id, "state": "queued"})},
        )
        session.commit()
        session.refresh(fight)
        _attach_fighter_names(session, [fight])
        return fight

    return run_db_query(_query)


def set_fight_pid(fight_id: int, pid: int) -> None:
    def _query(session):
        session.execute(
            text("UPDATE fights SET pid = :pid WHERE id = :id"),
            {"pid": pid, "id": fight_id},
        )
        session.commit()

    run_db_query(_query)


def get_fight_pid(fight_id: int) -> int | None:
    def _query(session):
        row = session.execute(
            text("SELECT pid FROM fights WHERE id = :id"),
            {"id": fight_id},
        ).fetchone()
        return row[0] if row else None

    return run_db_query(_query)


# States in which a pipeline subprocess may legitimately still be running.
# ('labeling_in_progress'/'labeling_complete'/'completed'/'failed' all mean the
# subprocess has already exited.)
_ACTIVE_PIPELINE_STATES = (
    "queued", "detecting", "tracking", "pose", "corners", "scoreboard",
    "segmenting", "analyzing",
)


def get_active_pipeline_pids() -> List[tuple[int, int]]:
    """(fight_id, pid) for every fight whose pipeline may still be running.

    Used at backend startup to reconcile PIDs recorded before a restart.
    """
    def _query(session):
        rows = session.execute(
            text(
                "SELECT id, pid FROM fights "
                "WHERE pid IS NOT NULL AND state IN :states"
            ).bindparams(bindparam("states", expanding=True)),
            {"states": list(_ACTIVE_PIPELINE_STATES)},
        ).fetchall()
        return [(r.id, r.pid) for r in rows]

    return run_db_query(_query)


def fail_stale_pipeline(fight_id: int, expected_pid: int) -> None:
    """Mark a fight failed because its recorded pipeline process is no longer
    running (e.g. it died along with a previous backend process). Only applies
    if the pid hasn't already moved on (avoids a race with a fresh re-upload)."""
    def _query(session):
        import json
        row = session.execute(
            text(
                "UPDATE fights SET state = 'failed', pid = NULL "
                "WHERE id = :id AND pid = :pid "
                "RETURNING id"
            ),
            {"id": fight_id, "pid": expected_pid},
        ).fetchone()
        if row is None:
            session.rollback()
            return
        session.execute(
            text("SELECT pg_notify('fight_state', :payload)"),
            {"payload": json.dumps({"id": fight_id, "state": "failed"})},
        )
        session.commit()

    run_db_query(_query)


def finish_labeling(fight_id: int) -> Fight | None:
    def _query(session):
        import json
        row = session.execute(
            text(
                "UPDATE fights SET state = 'labeling_complete' "
                "WHERE id = :id AND state = 'labeling_in_progress' "
                "RETURNING id"
            ),
            {"id": fight_id},
        ).fetchone()
        if row is None:
            session.rollback()
            return None
        session.execute(
            text("SELECT pg_notify('fight_state', :payload)"),
            {"payload": json.dumps({"id": fight_id, "state": "labeling_complete"})},
        )
        session.commit()
        fight = session.query(Fight).filter(Fight.id == fight_id).first()
        _attach_fighter_names(session, [fight])
        return fight

    return run_db_query(_query)


def delete_fight(fight_id: int) -> str | None:
    def _query(session):
        result = session.execute(
            text("DELETE FROM fights WHERE id = :id RETURNING video_path"),
            {"id": fight_id},
        )
        session.commit()
        row = result.fetchone()
        return row[0] if row else None

    return run_db_query(_query)
