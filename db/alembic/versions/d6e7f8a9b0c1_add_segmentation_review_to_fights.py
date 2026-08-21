"""Add segmentation review flags to fights

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-08-16 00:00:00.000000

Round segmentation can produce a confident-looking round list from a signal
that never actually corroborated it — when scoreboard OCR fails entirely, the
round count falls back to fighter-detection heuristics, which split a round on
any long camera cutaway. That output is indistinguishable in the database from
a clock-verified one, so it reaches the annotation UI unflagged and is only
caught by eye.

`segmentation_needs_review` records the pipeline's own verdict on whether a
human should confirm the rounds; `segmentation_review_reason` carries the
explanation shown in the UI. Both are written by the pipeline at segmentation
time and are never modified by labelling.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd6e7f8a9b0c1'
down_revision: Union[str, Sequence[str], None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'fights',
        sa.Column(
            'segmentation_needs_review',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )
    op.add_column(
        'fights',
        sa.Column('segmentation_review_reason', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('fights', 'segmentation_review_reason')
    op.drop_column('fights', 'segmentation_needs_review')
