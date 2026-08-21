"""Add labeled_at and video-validation columns to fights

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-12 00:10:00.000000

`labeled_at` is a durable marker for "this fight has finalised ground truth",
independent of `state` — `state` resets to 'queued'/'completed' whenever a
labelled fight is re-run through the AI pipeline to produce an evaluation
fixture (see plan 0a), so nothing that means "has ground truth" can be keyed
off `state` alone.

`reported_frames` / `decoded_frames` persist the full-decode validation
result (see eval/videocheck.py) so an INVALID fight can show *why* it was
rejected instead of a bare badge.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fights', sa.Column('labeled_at', sa.TIMESTAMP(), nullable=True))
    op.add_column('fights', sa.Column('reported_frames', sa.Integer(), nullable=True))
    op.add_column('fights', sa.Column('decoded_frames', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('fights', 'decoded_frames')
    op.drop_column('fights', 'reported_frames')
    op.drop_column('fights', 'labeled_at')
