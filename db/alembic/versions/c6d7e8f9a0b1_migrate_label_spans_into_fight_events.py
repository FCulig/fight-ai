"""Migrate label_spans rows into fight_events

Revision ID: c6d7e8f9a0b1
Revises: b4c5d6e7f8a9
Create Date: 2026-09-12 00:00:03.000000

Copies every label_spans row into fight_events as source='label',
kind=<the span's own kind> ('round'|'corner_swap'|'excluded' — the same
three values the new `kind` column's CHECK constraint will enforce, added
unchanged). start_frame becomes `frame` (see a3b4c5d6e7f8's docstring for why
`frame` isn't renamed to start_frame); end_frame and value map straight
across. description/fighter_id/action/success/state/corner/target/labeler
all stay NULL — spans never had any of those.

New primary keys are issued; nothing holds a foreign key to label_spans.id.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c6d7e8f9a0b1'
down_revision: Union[str, Sequence[str], None] = 'b4c5d6e7f8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO fight_events
            (fight_id, frame, end_frame, description, fighter_id, action,
             success, state, source, kind, corner, target, value, labeler,
             created_at)
        SELECT
            fight_id, start_frame, end_frame, NULL, NULL, NULL,
            NULL, NULL, 'label', kind, NULL, NULL, value, NULL,
            created_at
        FROM label_spans
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM fight_events WHERE source = 'label' "
        "AND kind IN ('round', 'corner_swap', 'excluded')"
    )
