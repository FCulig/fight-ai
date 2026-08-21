"""Build a FightLabels object from the DB-backed label_events/label_spans
tables the Annotate UI writes, instead of a hand-edited JSON file.

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
# label_events.target (already head/body/leg at label time via the Shift
# modifier or the kick's fixed target — see taxonomy.ts) rather than derived
# here; NULL maps to "unknown" per plan 0c(3).
#
# jab/cross are lead/rear-relative (boxing terms), matching the pipeline's own
# classify_punch_type() — so this works correctly for southpaws without any
# stance tracking. Hooks/uppercuts stay absolute left/right in the palette
# (directly observable, no stance judgment needed) but both hands collapse to
# the same family here, so handedness never reaches the training label.
#
# clinch_punch/ground_punch/ground_knee map to the same non-specific
# "punch"/"knee" families the pipeline itself uses for these positions
# (PIPELINE_ACTION_MAP) — matching real MMA-stats convention, not just the
# rule cascade's limitation: a scramble genuinely isn't a clean jab/hook, so
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

        for r in db.execute(
            text("SELECT start_frame, end_frame, value FROM label_spans "
                 "WHERE fight_id = :fid AND kind = 'round' ORDER BY start_frame"),
            {"fid": fight_id},
        ):
            if r.end_frame is None:
                continue  # never happens for round spans (seeded fully-formed), guard anyway
            labels.rounds.append(Round(
                start=r.start_frame, end=r.end_frame,
                round=int(r.value) if r.value else 1,
            ))

        for e in db.execute(
            text("SELECT start_frame, end_frame, value FROM label_spans "
                 "WHERE fight_id = :fid AND kind = 'excluded' ORDER BY start_frame"),
            {"fid": fight_id},
        ):
            if e.end_frame is None:
                continue  # left open by mistake — export skips it rather than guessing an end
            labels.excluded.append(Excluded(start=e.start_frame, end=e.end_frame, reason=e.value or ""))

        for c in db.execute(
            text("SELECT start_frame, end_frame FROM label_spans "
                 "WHERE fight_id = :fid AND kind = 'corner_swap' ORDER BY start_frame"),
            {"fid": fight_id},
        ):
            if c.end_frame is None:
                continue
            labels.corner_swaps.append(Span(start=c.start_frame, end=c.end_frame))

        events = db.execute(
            text("SELECT frame, corner, action, target, success FROM label_events "
                 "WHERE fight_id = :fid ORDER BY frame, id"),
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
    finally:
        db.close()
