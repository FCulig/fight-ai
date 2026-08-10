"""Add pid to fights

Revision ID: e5f6a7b8c9d0
Revises: d1e2f3a4b5c6
Create Date: 2026-08-08 00:00:00.000000

Persists the PID of the spawned AI pipeline subprocess so it survives a
backend restart: it lets DELETE /fights/{id} kill an in-progress pipeline
and lets startup reconciliation detect a pipeline that died with the
backend and mark it failed instead of leaving the fight stuck.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fights', sa.Column('pid', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('fights', 'pid')
