"""Create eval_runs table

Revision ID: b4ea83f7c87b
Revises: f0a1b2c3d4e5
Create Date: 2026-09-14 00:00:00.000000

Pipeline accuracy has so far only ever lived as CLI output
(`python -m eval.cli score <video>`) or a hand-saved JSON file under
`ai/eval/baselines/`. Neither is queryable, so comparing accuracy across
pipeline versions over time meant opening files by hand. `eval_runs` persists
every scored run so the frontend (Training Lab §E, "Pipeline accuracy") can
list a fixture's history and plot it.

A "fixture" is a `fights` row with `purpose = 'reference'` — the hand-labelled
video that is never re-run, only ever scored against. `reference_fight_id` is
that row; `scored_fight_id` is the separate `purpose = 'ai_labeled'` fight
(the same source video re-uploaded through a newer pipeline version) whose
predictions were scored against it. This mirrors the workflow documented in
backend/CLAUDE.md: accuracy is measured across two different fight ids, never
by re-processing a labelled fight in place.

`report` stores the exact `report` sub-object `ai/eval/report_io.save_report()`
already produces (`dataclasses.asdict()` plus its `family_confusion`/
`state.confusion` tuple-key-to-string transform) — so a DB row and a checked-in
`ai/eval/baselines/*.json` file are shape-identical, and no relational
normalisation of the nested score structure is attempted here: every accuracy
panel (headline F1, per-family confusion, timing, rounds, ...) needs a
different slice of it, and that shape will keep changing as score.py does.

No uniqueness constraint: this is an append-only log, matching the append-only
spirit of the baseline JSON files — multiple runs of the same pipeline version
are allowed, and the frontend dedupes to "latest per scored fight" itself (each
scored fight is one pipeline version; `git_sha` is only the scorer's HEAD).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'b4ea83f7c87b'
down_revision: Union[str, Sequence[str], None] = 'f0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'eval_runs',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('reference_fight_id', sa.Integer,
                  sa.ForeignKey('fights.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scored_fight_id', sa.Integer,
                  sa.ForeignKey('fights.id', ondelete='CASCADE'), nullable=False),
        sa.Column('git_sha', sa.String(40), nullable=False),
        sa.Column('constants_sha256', sa.String(64), nullable=False),
        sa.Column('tolerance_secs', sa.Float, nullable=False),
        sa.Column('tolerance_frames', sa.Integer, nullable=False),
        sa.Column('scored_minutes', sa.Float, nullable=False),
        sa.Column('report', JSONB, nullable=False),
        sa.Column('generated_at', sa.TIMESTAMP, nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('triggered_by', sa.String(200), nullable=True),
    )
    op.create_index(
        'ix_eval_runs_reference_fight',
        'eval_runs',
        ['reference_fight_id', 'generated_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_eval_runs_reference_fight', table_name='eval_runs')
    op.drop_table('eval_runs')
