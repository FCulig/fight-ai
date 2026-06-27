"""Add structured columns (fighter_id, action, success) to fight_events

Revision ID: c3d4e5f6a7b8
Revises: c2d3e4f5a6b7
Create Date: 2026-06-27 00:00:02.000000

Adds queryable structured columns alongside the existing free-form
``description`` (which stays NOT NULL). ``fighter_id`` and ``success`` are
nullable: round boundaries and fight-state events leave them NULL, strikes
populate them. Existing rows get NULL for all three new columns —
re-processing a fight repopulates them.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fight_events', sa.Column('fighter_id', sa.Integer, nullable=True))
    op.add_column('fight_events', sa.Column('action', sa.String(50), nullable=True))
    op.add_column('fight_events', sa.Column('success', sa.Boolean, nullable=True))
    op.create_foreign_key(
        'fk_fight_events_fighter_id', 'fight_events', 'fighters',
        ['fighter_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_fight_events_fighter_id', 'fight_events', ['fighter_id'])
    op.create_index('ix_fight_events_fighter_action', 'fight_events',
                    ['fighter_id', 'action'])


def downgrade() -> None:
    op.drop_index('ix_fight_events_fighter_action', table_name='fight_events')
    op.drop_index('ix_fight_events_fighter_id', table_name='fight_events')
    op.drop_constraint('fk_fight_events_fighter_id', 'fight_events', type_='foreignkey')
    op.drop_column('fight_events', 'success')
    op.drop_column('fight_events', 'action')
    op.drop_column('fight_events', 'fighter_id')
