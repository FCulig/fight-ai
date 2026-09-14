"""Drop label_events and label_spans tables

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-09-12 00:00:05.000000

Final step of the fight_events/label_events/label_spans merge. Both tables'
data has already been copied into fight_events (source='label') by the two
migrations earlier in this chain. This must land in the same deploy as the
backend/AI code changes that stop reading/writing these two tables —
label_event_service.py, label_span_service.py, and the /label-events/ and
/label-spans/ routes cannot still be in service when this runs.

Downgrade recreates empty tables (schema only) — it does not restore data;
by the time a downgrade would run, fight_events already holds the
authoritative copy of everything these tables held.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e8f9a0b1c2d3'
down_revision: Union[str, Sequence[str], None] = 'd7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('ix_label_events_fight_id', table_name='label_events')
    op.drop_table('label_events')
    op.drop_index('ix_label_spans_fight_id', table_name='label_spans')
    op.drop_table('label_spans')


def downgrade() -> None:
    op.create_table(
        'label_events',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('fight_id', sa.Integer(), sa.ForeignKey('fights.id', ondelete='CASCADE'), nullable=False),
        sa.Column('frame', sa.Integer(), nullable=False),
        sa.Column('corner', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=True),
        sa.Column('target', sa.String(length=10), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('labeler', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_label_events_fight_id', 'label_events', ['fight_id'])

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
