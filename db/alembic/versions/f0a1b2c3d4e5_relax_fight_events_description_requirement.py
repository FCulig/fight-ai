"""Only require description for fight_end; NULL it out everywhere else

Revision ID: f0a1b2c3d4e5
Revises: e8f9a0b1c2d3
Create Date: 2026-09-13 00:00:00.000000

`description` was a frozen string, baked in once at write time from a fixed
name mapping. That's a problem specifically for corner-attributed events: a
`corner_swap` label span can be added or edited *after* a strike was already
logged, and the stored text has no way to reflect that — Player/Annotate were
showing a stale, possibly wrong fighter name even after the box overlay
itself was display-corrected (see FighterOverlay's cornerSwapSpans).

The fix is to stop trusting stored text and reconstruct it at display time
instead (frontend/src/utils/describeEvent.ts), from action/target/corner
(labels) or action/fighter_id/success/state (predictions) plus the `rounds`
table for round markers. `fight_end` is the one exception: it's manual-only
(the AI pipeline can never emit it) and carries free-form winner/method/detail
that has no structured column to rebuild from, so it keeps a real stored
description — enforced by the CHECK below instead of the previous blanket
"every point event needs one".

The AI pipeline (ai/fight_processing/fight_processing.py) and the Annotate
write path (backend's FightEventCreate validator, frontend's logTool()) were
already updated in the same change to stop populating description for
anything but fight_end — this migration is what makes existing rows and the
schema itself agree.

Downgrade note: restoring the old blanket constraint is only meaningful
against data where every point row still has a description. Since this
migration NULLs that out for everything but fight_end, downgrading without
first restoring that text from another source (there isn't one) will fail
its own CHECK the moment it's applied. Documented here rather than papered
over with a fake-successful downgrade.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f0a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'e8f9a0b1c2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Constraint must be relaxed before the UPDATE — the old blanket
    # "every point row needs a description" CHECK is still live at this
    # point in the migration and would reject the NULLing UPDATE below.
    op.drop_constraint('ck_fight_events_point_has_description', 'fight_events', type_='check')
    op.create_check_constraint(
        'ck_fight_events_point_has_description', 'fight_events',
        "NOT (kind = 'point' AND action = 'fight_end') OR description IS NOT NULL",
    )
    op.execute(
        "UPDATE fight_events SET description = NULL "
        "WHERE kind = 'point' AND (action IS DISTINCT FROM 'fight_end')"
    )


def downgrade() -> None:
    op.drop_constraint('ck_fight_events_point_has_description', 'fight_events', type_='check')
    op.create_check_constraint(
        'ck_fight_events_point_has_description', 'fight_events',
        "kind <> 'point' OR description IS NOT NULL",
    )
