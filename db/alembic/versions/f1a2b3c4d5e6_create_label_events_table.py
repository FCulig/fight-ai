"""Create label_events table, separate from fight_events

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-08-12 00:00:00.000000

Hand annotations were being written into fight_events, the same table
process_fight() opens with `DELETE FROM fight_events WHERE fight_id = :fid`
and rewrites on every pipeline run. Re-running the AI pipeline over a
labelled fight — the scoring path — silently destroyed every hand label.

label_events is the ground-truth counterpart of fight_events: the Annotate
page now reads/writes only this table, the Player continues to read only
fight_events, and the two never mix. `corner` (0=red, 1=blue) rather than
`fighter_id` because that's what the labeller can see and what matches
`fighter_frames.corner`; fighter identity is derivable from the fights row
when needed. `target` and `success` are added now (rather than in a later
migration) since they're part of the same table shape — see plan 0c(3)/0c(1)
for when they start being populated with real values.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index('ix_label_events_fight_id', table_name='label_events')
    op.drop_table('label_events')
