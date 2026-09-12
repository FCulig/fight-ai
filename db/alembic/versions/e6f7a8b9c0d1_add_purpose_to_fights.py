"""Add purpose to fights

Revision ID: e6f7a8b9c0d1
Revises: d6e7f8a9b0c1
Create Date: 2026-09-12 00:00:00.000000

What a video is *for* was never stored. The upload dialog sends `mode`
('ai' | 'manual'), but that field is write-only — it picks `skip_events` on the
spawned subprocess and is then discarded. The only after-the-fact signal was
`state`, and it is lossy in both directions: a manual-track fight still in
`detecting` is indistinguishable from an AI one, and a hand-labelled fight gets
re-run through the full AI pipeline to become an evaluation fixture, which
resets `state` to 'queued' and then 'completed' — erasing the distinction
entirely.

That matters because Stage 0's central rule is that training and evaluation
sets stay disjoint (no fight is ever both), and nothing in the schema could
express it. `labeled_at` records *that* a fight has ground truth, not what the
ground truth is for.

`purpose` is that missing record: 'training_data' (labels feed model training),
'reference' (held out of training, scored against to measure pipeline accuracy)
or 'ai_labeled' (produced by the full AI pipeline). It is written once by
POST /fights/upload and never again — in particular `run_pipeline`'s
ON CONFLICT (video_path) DO UPDATE must never add it to its SET list, or a
reference fight would lose its identity the first time it is scored. Same
durability rule as `labeled_at`.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, Sequence[str], None] = 'd6e7f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'fights',
        sa.Column(
            'purpose',
            sa.String(32),
            nullable=False,
            server_default=sa.text("'ai_labeled'"),
        ),
    )
    # Rows created by the pipeline CLI (single-file mode, or run_batch's
    # fight_videos/ registration) are AI-processed by definition, so the server
    # default is right for them and for every future CLI-created row. The rows
    # already in this database are not: all but fight 31 were hand-labelled to
    # become training data.
    op.execute("UPDATE fights SET purpose = 'training_data' WHERE id <> 31")


def downgrade() -> None:
    op.drop_column('fights', 'purpose')
