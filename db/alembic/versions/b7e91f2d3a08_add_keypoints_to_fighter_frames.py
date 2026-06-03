"""Add keypoints column to fighter_frames

Revision ID: b7e91f2d3a08
Revises: a1b2c3d4e5f6
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e91f2d3a08'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'fighter_frames',
        sa.Column('keypoints', sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column('fighter_frames', 'keypoints')
