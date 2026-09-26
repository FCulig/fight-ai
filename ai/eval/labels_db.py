"""Build a FightLabels object from the DB-backed fight_events rows (source=
'label') the Annotate UI writes, instead of a hand-edited JSON file.

`python -m eval.cli export <video>` is the entry point that writes the result
to eval/labels/*.json for git — see cli.py. Refuses any fight with
labeled_at IS NULL (plan 0c-2): that column, not `state`, is the durable
"this fight has finalised ground truth" marker, since `state` gets reset the
moment a labelled fight is re-run through the AI pipeline to become an
evaluation fixture (plan 0a).
"""

from sqlalchemy import text

from database import SessionLocal

from .predictions import lookup_fight
from .schema import Excluded, FightLabels, Round, Span, StateSpan, Strike, Takedown

# Palette action -> strike family. `target` is read straight off
# fight_events.target (source='label'; already head/body/leg at label time
# via the Shift modifier or the kick's fixed target — see taxonomy.ts) rather
# than derived here; NULL maps to "unknown" per plan 0c(3).
#
# jab/cross are lead/rear-relative (boxing terms), matching the pipeline's own
# strike model's classes — so this works correctly for southpaws without any
# stance tracking. Hooks/uppercuts stay absolute left/right in the palette
# (directly observable, no stance judgment needed) but both hands collapse to
# the same family here, so handedness never reaches the training label.
#
# clinch_punch/ground_punch/ground_knee map to the same non-specific
# "punch"/"knee" families the pipeline itself uses for these positions
# (PIPELINE_ACTION_MAP) — matching real MMA-stats convention, not just the
# old rule cascade's limitation: a scramble genuinely isn't a clean jab/hook, so
# forcing that classification would fabricate precision that isn't there.
# `target` is always None for these (no hasTarget/fixedTarget in taxonomy.ts)
# -> "unknown" below, same as the pipeline's grappling predictions, so
# Strike.is_specific is False on both sides and they're excluded from the
# family/target accuracy denominators rather than penalising either side for
# a distinction neither attempts.
LABEL_FAMILY_MAP: dict[str, str] = {
    "jab": "jab",
    "cross": "cross",
    "left_hook": "hook",
    "right_hook": "hook",
    "left_uppercut": "uppercut",
    "right_uppercut": "uppercut",
    "calf_kick": "kick",
    "low_kick": "kick",
    "middle_kick": "kick",
    "high_kick": "kick",
    "elbow": "elbow",
    "clinch_knee": "knee",
    "ground_knee": "knee",
    "clinch_punch": "punch",
    "ground_punch": "punch",
}

STATE_ACTION_MAP = {
    "state_striking": "STRIKING",
    "state_clinch": "CLINCH",
    "state_ground": "GROUND",
}


class NotLabeled(Exception):
    """Raised when a fight has no `labeled_at` — it hasn't finished Annotate."""


def build_labels(video: str) -> FightLabels:
    db = SessionLocal()
    try:
        fight_id, video_path, fps, _ = lookup_fight(db, video)
        return _build_labels(db, fight_id, video_path, fps)
    finally:
        db.close()


def build_labels_by_fight_id(fight_id: int) -> FightLabels:
    """Same as `build_labels`, but resolves by fight id directly instead of a
    video path/stem — the two fights the real workflow needs to score against
    each other (a `purpose='reference'` upload and a later `purpose=
    'ai_labeled'` re-upload of the same source video) don't share a
    `video_path`, so `lookup_fight`'s stem match can't join them. See
    `score-pair` in cli.py, the entry point that actually needs this."""
    db = SessionLocal()
    try:
        row = db.execute(
            text("SELECT video_path, fps FROM fights WHERE id = :fid"),
            {"fid": fight_id},
        ).first()
        if row is None:
            raise LookupError(f"No fights row with id={fight_id}")
        return _build_labels(db, fight_id, row.video_path, int(row.fps))
    finally:
        db.close()


def _build_labels(db, fight_id: int, video_path: str, fps: int) -> FightLabels:
    row = db.execute(
        text("SELECT labeled_at FROM fights WHERE id = :fid"), {"fid": fight_id}
    ).first()
    if row is None or row.labeled_at is None:
        raise NotLabeled(
            f"{video_path} has no labeled_at yet — finish labeling in the "
            f"UI first (POST /fights/{fight_id}/finish-labeling)"
        )

    labels = FightLabels(video=video_path, fps=fps, labeled_at=str(row.labeled_at))

    # The highest frame the pipeline wrote a fighter box for — manual-track
    # fights still write fighter_frames (plan 0a), so this is available
    # even though strike detection was skipped.
    fc = db.execute(
        text("SELECT MAX(frame) AS mx FROM fighter_frames WHERE fight_id = :fid"),
        {"fid": fight_id},
    ).scalar()
    labels.frame_count = int(fc or 0)

    # Only signal available for round-circularity detection: a label round
    # whose bounds are still byte-identical to the AI `rounds` row it was
    # seeded from (event_service._ensure_round_events_seeded) has never been
    # touched by a labeller. False-negative on a labeller who reviewed and
    # left it unchanged — accepted, since it errs toward more "unverified"
    # rounds, never fewer. See Round.seeded's docstring.
    ai_rounds = {
        row.round_number: (row.start_frame, row.end_frame)
        for row in db.execute(
            text("SELECT round_number, start_frame, end_frame FROM rounds "
                 "WHERE fight_id = :fid"),
            {"fid": fight_id},
        )
    }

    for r in db.execute(
        text("SELECT frame AS start_frame, end_frame, value FROM fight_events "
             "WHERE fight_id = :fid AND source = 'label' AND kind = 'round' "
             "ORDER BY frame"),
        {"fid": fight_id},
    ):
        if r.end_frame is None:
            continue  # never happens for round spans (seeded fully-formed), guard anyway
        round_num = int(r.value) if r.value else 1
        ai_bounds = ai_rounds.get(round_num)
        seeded = ai_bounds is not None and (r.start_frame, r.end_frame) == ai_bounds
        labels.rounds.append(Round(
            start=r.start_frame, end=r.end_frame,
            round=round_num, seeded=seeded,
        ))

    for e in db.execute(
        text("SELECT frame AS start_frame, end_frame, value FROM fight_events "
             "WHERE fight_id = :fid AND source = 'label' AND kind = 'excluded' "
             "ORDER BY frame"),
        {"fid": fight_id},
    ):
        if e.end_frame is None:
            continue  # left open by mistake — export skips it rather than guessing an end
        labels.excluded.append(Excluded(start=e.start_frame, end=e.end_frame, reason=e.value or ""))

    for c in db.execute(
        text("SELECT frame AS start_frame, end_frame FROM fight_events "
             "WHERE fight_id = :fid AND source = 'label' AND kind = 'corner_swap' "
             "ORDER BY frame"),
        {"fid": fight_id},
    ):
        if c.end_frame is None:
            continue
        labels.corner_swaps.append(Span(start=c.start_frame, end=c.end_frame))

    events = db.execute(
        text("SELECT frame, corner, action, target, success FROM fight_events "
             "WHERE fight_id = :fid AND source = 'label' AND kind = 'point' "
             "ORDER BY frame, id"),
        {"fid": fight_id},
    ).all()

    # State marks are change points, not spans: each runs to the next, and
    # the last runs to the end of its round (plan 0c-4 point 4).
    state_marks = [e for e in events if e.action in STATE_ACTION_MAP]
    for i, e in enumerate(state_marks):
        if i + 1 < len(state_marks):
            end = state_marks[i + 1].frame - 1
        else:
            r = next((r for r in labels.rounds if r.contains(e.frame)), None)
            end = r.end if r else labels.frame_count
        labels.states.append(StateSpan(start=e.frame, end=end, state=STATE_ACTION_MAP[e.action]))

    for e in events:
        if e.action == "takedown_landed":
            labels.takedowns.append(Takedown(
                frame=e.frame,
                fighter="red" if e.corner == 0 else "blue",
            ))
            continue

        family = LABEL_FAMILY_MAP.get(e.action)
        if family is None:
            continue  # state/takedown_attempt/_defended/knockdown/fight_end — not part of the schema yet
        labels.strikes.append(Strike(
            frame=e.frame,
            fighter="red" if e.corner == 0 else "blue",
            family=family,
            target=e.target or "unknown",
            landed=e.success,
        ))

    labels.validate()
    return labels
