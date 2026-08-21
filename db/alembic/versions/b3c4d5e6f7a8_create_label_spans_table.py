"""Create label_spans table

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-13 00:00:00.000000

A strike is a moment (label_events). The things still missing are stretches
of frames — human-verified round bounds, corner-swap overrides, mid-round
replay/excluded stretches — all of the shape (start, end, what), so they
share one table with a `kind` column. See plan 0d.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'label_spans',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('fight_id', sa.Integer(), sa.ForeignKey('fights.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('start_frame', sa.Integer(), nullable=False),
        sa.Column('end_frame', sa.Integer(), nullable=True),
        sa.Column('value', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_label_spans_fight_id', 'label_spans', ['fight_id'])


def downgrade() -> None:
    op.drop_index('ix_label_spans_fight_id', table_name='label_spans')
    op.drop_table('label_spans')
