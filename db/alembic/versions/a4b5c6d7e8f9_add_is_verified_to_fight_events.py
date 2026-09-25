"""Add is_verified column to fight_events

Revision ID: a4b5c6d7e8f9
Revises: b4ea83f7c87b
Create Date: 2026-09-15 00:00:00.000000

Backs the Training Data QA page: a reviewer replays a hand-labelled point
event's clip and marks it training-worthy (True) or drops it (False).
NULL means not reviewed yet. Deliberately a plain nullable bool, not scoped
to `kind='point'` at the schema level — the service layer enforces that,
same pattern as `corner`/`fighter_id`'s source-scoping.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a4b5c6d7e8f9'
down_revision: Union[str, Sequence[str], None] = 'b4ea83f7c87b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fight_events', sa.Column('is_verified', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('fight_events', 'is_verified')
