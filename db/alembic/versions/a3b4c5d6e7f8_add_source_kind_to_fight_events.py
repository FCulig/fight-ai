"""Add source/kind and label-shaped columns to fight_events

Revision ID: a3b4c5d6e7f8
Revises: e6f7a8b9c0d1
Create Date: 2026-09-12 00:00:01.000000

First step of merging label_events and label_spans into fight_events (see
ai/CLAUDE.md and backend/CLAUDE.md for the full rationale). fight_events was
pipeline-only; label_events/label_spans were hand-authored and physically
separated specifically so a pipeline re-run could never destroy a label and
so a query couldn't accidentally blend the two. That physical separation is
being traded for a simpler single-table model now that fights are never
re-run through the pipeline (accuracy is validated by uploading the same
video twice under different `purpose`s and comparing across fight_id, not by
re-processing a labelled fight in place) — the same safety property is
recovered here via two discriminator columns instead: `source`
('prediction'|'label' — WHO wrote the row, safety-critical) and `kind`
('point'|'round'|'corner_swap'|'excluded' — WHAT SHAPE the row is, extending
label_spans' existing three-value enum with a fourth for ordinary point
events).

This migration only adds columns and backfills existing rows as
source='prediction', kind='point' (correct for every row that exists today).
Data is moved in from label_events/label_spans by the next two migrations;
CHECK constraints land after that, once the real data is known to satisfy
them (label_events.corner and label_spans.kind were never DB-constrained
before now).

`end_frame` reuses `frame` as an implicit "start_frame" for range-kind rows
rather than renaming `frame` — renaming would touch every raw-SQL query in
ai/fight_processing and ai/eval, plus every frontend `Event.frame` reference,
for no real benefit. `description` drops its NOT NULL because label_spans
rows never had free text and shouldn't get synthesized text now (a new
regex-parsing surface is exactly what this codebase is trying to get away
from) — a CHECK in a later migration re-enforces "every kind='point' row
still has one."

created_at is new for prediction rows; every fight_events row that exists
before this migration runs gets this migration's execution time as its
created_at, since the real write time was never recorded. That's accepted,
documented data loss — nothing orders by it today.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fight_events', sa.Column(
        'source', sa.String(20), nullable=False, server_default=sa.text("'prediction'"),
    ))
    op.add_column('fight_events', sa.Column(
        'kind', sa.String(20), nullable=False, server_default=sa.text("'point'"),
    ))
    op.add_column('fight_events', sa.Column('end_frame', sa.Integer(), nullable=True))
    op.add_column('fight_events', sa.Column('corner', sa.Integer(), nullable=True))
    op.add_column('fight_events', sa.Column('target', sa.String(10), nullable=True))
    op.add_column('fight_events', sa.Column('value', sa.String(200), nullable=True))
    op.add_column('fight_events', sa.Column('labeler', sa.String(100), nullable=True))
    op.add_column('fight_events', sa.Column(
        'created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('now()'),
    ))
    op.alter_column('fight_events', 'description', nullable=True)


def downgrade() -> None:
    op.alter_column('fight_events', 'description', nullable=False)
    op.drop_column('fight_events', 'created_at')
    op.drop_column('fight_events', 'labeler')
    op.drop_column('fight_events', 'value')
    op.drop_column('fight_events', 'target')
    op.drop_column('fight_events', 'corner')
    op.drop_column('fight_events', 'end_frame')
    op.drop_column('fight_events', 'kind')
    op.drop_column('fight_events', 'source')
