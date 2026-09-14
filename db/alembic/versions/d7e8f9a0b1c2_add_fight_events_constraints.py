"""Add CHECK constraints and indexes enforcing fight_events' source/kind shape

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-09-12 00:00:04.000000

label_events.corner and label_spans.kind were never DB-constrained before
this migration chain — before running this in a real environment, verify
both of the following return zero rows, or these CHECKs will fail to apply:

    SELECT DISTINCT corner FROM fight_events
    WHERE source = 'label' AND corner IS NOT NULL AND corner NOT IN (0, 1);

    SELECT DISTINCT kind FROM fight_events
    WHERE kind NOT IN ('point', 'round', 'corner_swap', 'excluded');

The constraints, and what each one is actually for:

- ck_fight_events_source / ck_fight_events_kind: close the two enums.
- ck_fight_events_point_has_description: every kind='point' row (prediction
  or label) keeps requiring a description, same as both fight_events and
  label_events always did; range rows (round/corner_swap/excluded) never had
  one and still don't.
- ck_fight_events_point_has_no_end_frame: only range kinds use end_frame.
- ck_fight_events_corner_range / ck_fight_events_corner_is_label_only: corner
  is a labeller's track-slot click (0=red/1=blue), never a resolved fighter
  identity — see fighter_id below. It only ever appears on source='label'
  rows.
- ck_fight_events_fighter_id_is_prediction_only: fighter_id is a resolved
  identity (FK to fighters), only ever written by the AI pipeline.

Together the last two constraints are the DB-level version of the
corner-vs-fighter_id distinction this codebase has documented since
label_events was first split out: a labeller's box click and a pipeline's
resolved person can never end up in the same column.

source/kind drop their column default here, once every existing row has been
backfilled/migrated — every future INSERT (pipeline raw SQL, or the unified
event_service) must state both explicitly from here on. A lingering default
would silently mislabel a forgotten write.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, Sequence[str], None] = 'c6d7e8f9a0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        'ck_fight_events_source', 'fight_events', "source IN ('prediction', 'label')",
    )
    op.create_check_constraint(
        'ck_fight_events_kind', 'fight_events',
        "kind IN ('point', 'round', 'corner_swap', 'excluded')",
    )
    op.create_check_constraint(
        'ck_fight_events_point_has_description', 'fight_events',
        "kind <> 'point' OR description IS NOT NULL",
    )
    op.create_check_constraint(
        'ck_fight_events_point_has_no_end_frame', 'fight_events',
        "kind <> 'point' OR end_frame IS NULL",
    )
    op.create_check_constraint(
        'ck_fight_events_corner_range', 'fight_events',
        "corner IS NULL OR corner IN (0, 1)",
    )
    op.create_check_constraint(
        'ck_fight_events_corner_is_label_only', 'fight_events',
        "corner IS NULL OR source = 'label'",
    )
    op.create_check_constraint(
        'ck_fight_events_fighter_id_is_prediction_only', 'fight_events',
        "fighter_id IS NULL OR source = 'prediction'",
    )

    op.alter_column('fight_events', 'source', server_default=None)
    op.alter_column('fight_events', 'kind', server_default=None)

    op.create_index('ix_fight_events_fight_source', 'fight_events', ['fight_id', 'source'])
    op.create_index('ix_fight_events_fight_kind', 'fight_events', ['fight_id', 'kind'])


def downgrade() -> None:
    op.drop_index('ix_fight_events_fight_kind', table_name='fight_events')
    op.drop_index('ix_fight_events_fight_source', table_name='fight_events')

    op.alter_column('fight_events', 'kind', server_default='point')
    op.alter_column('fight_events', 'source', server_default='prediction')

    op.drop_constraint('ck_fight_events_fighter_id_is_prediction_only', 'fight_events', type_='check')
    op.drop_constraint('ck_fight_events_corner_is_label_only', 'fight_events', type_='check')
    op.drop_constraint('ck_fight_events_corner_range', 'fight_events', type_='check')
    op.drop_constraint('ck_fight_events_point_has_no_end_frame', 'fight_events', type_='check')
    op.drop_constraint('ck_fight_events_point_has_description', 'fight_events', type_='check')
    op.drop_constraint('ck_fight_events_kind', 'fight_events', type_='check')
    op.drop_constraint('ck_fight_events_source', 'fight_events', type_='check')
