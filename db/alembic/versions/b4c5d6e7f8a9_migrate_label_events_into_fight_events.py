"""Migrate label_events rows into fight_events

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-09-12 00:00:02.000000

Copies every label_events row into fight_events as source='label',
kind='point'. New primary keys are issued — nothing in the codebase holds a
foreign key to label_events.id, and the only client-side thing that ever
cached one (Annotate's optimistic-update local state) is rebuilt from a
fresh fetch, not persisted, so renumbering is safe.

label_events.corner/target/labeler/success map straight across; fighter_id
and state stay NULL (label rows never had a resolved fighter identity or a
state column — see the CHECK constraints landing in a later migration).

label_events is not dropped here — that happens once the backend/AI code no
longer reads or writes it, in the same deploy (see the final migration in
this chain).
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, Sequence[str], None] = 'a3b4c5d6e7f8'
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
            fight_id, frame, NULL, description, NULL, action,
            success, NULL, 'label', 'point', corner, target, NULL, labeler,
            created_at
        FROM label_events
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM fight_events WHERE source = 'label' AND kind = 'point'")
