"""Make fight_events.fight_id NOT NULL

Delete any legacy rows where fight_id IS NULL (rows written before the
fights table existed), then tighten the column to NOT NULL.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Remove legacy rows that have no fight association before tightening
    op.execute("DELETE FROM fight_events WHERE fight_id IS NULL")
    op.alter_column('fight_events', 'fight_id', nullable=False)


def downgrade() -> None:
    op.alter_column('fight_events', 'fight_id', nullable=True)
