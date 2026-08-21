"""Add structured state column to fight_events

Revision ID: c5d6e7f8a9b0
Revises: b3c4d5e6f7a8
Create Date: 2026-08-13 00:20:00.000000

eval/predictions.py previously recovered fight-state transitions by regex
over the free-text `description` column, because `action` is NULL for a
STRIKING transition (only takedown/clinch initiations get an action code).
That parser breaks silently if the description wording ever changes. This
column is the structured fix — see plan "Also worth doing".

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fight_events', sa.Column('state', sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column('fight_events', 'state')
