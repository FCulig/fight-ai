"""Add fights, fighter_frames, and rounds tables

Revision ID: a1b2c3d4e5f6
Revises: 92f72188aec1
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '92f72188aec1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'fights',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('video_path', sa.String(500), nullable=False, unique=True),
        sa.Column('fps', sa.Integer, nullable=False),
        sa.Column('width', sa.Integer, nullable=False),
        sa.Column('height', sa.Integer, nullable=False),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column('processed', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('processed_at', sa.TIMESTAMP, nullable=True),
    )

    op.create_table(
        'rounds',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('fight_id', sa.Integer, sa.ForeignKey('fights.id', ondelete='CASCADE'), nullable=False),
        sa.Column('round_number', sa.Integer, nullable=False),
        sa.Column('start_frame', sa.Integer, nullable=False),
        sa.Column('end_frame', sa.Integer, nullable=False),
        sa.UniqueConstraint('fight_id', 'round_number'),
    )

    op.create_table(
        'fighter_frames',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('fight_id', sa.Integer, sa.ForeignKey('fights.id', ondelete='CASCADE'), nullable=False),
        sa.Column('frame', sa.Integer, nullable=False),
        sa.Column('fighter_id', sa.Integer, nullable=False),
        sa.Column('x1', sa.Float, nullable=False),
        sa.Column('y1', sa.Float, nullable=False),
        sa.Column('x2', sa.Float, nullable=False),
        sa.Column('y2', sa.Float, nullable=False),
        sa.Column('confidence', sa.Float, nullable=True),
    )

    op.add_column('fight_events', sa.Column('fight_id', sa.Integer, sa.ForeignKey('fights.id', ondelete='CASCADE'), nullable=True))

    op.create_index('ix_fighter_frames_fight_frame', 'fighter_frames', ['fight_id', 'frame'])
    op.create_index('ix_rounds_fight_id', 'rounds', ['fight_id'])
    op.create_index('ix_fight_events_fight_id', 'fight_events', ['fight_id'])


def downgrade() -> None:
    op.drop_index('ix_fight_events_fight_id', table_name='fight_events')
    op.drop_index('ix_rounds_fight_id', table_name='rounds')
    op.drop_index('ix_fighter_frames_fight_frame', table_name='fighter_frames')

    op.drop_column('fight_events', 'fight_id')

    op.drop_table('fighter_frames')
    op.drop_table('rounds')
    op.drop_table('fights')
