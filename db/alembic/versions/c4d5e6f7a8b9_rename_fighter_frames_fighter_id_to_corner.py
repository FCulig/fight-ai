"""Rename fighter_frames.fighter_id to corner

Revision ID: c4d5e6f7a8b9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-27 00:00:03.000000

``fighter_frames.fighter_id`` was always a corner index (0=red, 1=blue), never
a fighter identity. Renaming it to ``corner`` frees ``fighter_id`` to mean
"FK to fighters" consistently across the schema.

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('fighter_frames', 'fighter_id', new_column_name='corner')


def downgrade() -> None:
    op.alter_column('fighter_frames', 'corner', new_column_name='fighter_id')
