"""Replace processed/processed_at with state column

Revision ID: d1e2f3a4b5c6
Revises: c4d5e6f7a8b9
Create Date: 2026-06-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fights', sa.Column('state', sa.String(32), nullable=False, server_default='queued'))
    op.drop_column('fights', 'processed')
    op.drop_column('fights', 'processed_at')


def downgrade() -> None:
    op.add_column('fights', sa.Column('processed_at', sa.TIMESTAMP, nullable=True))
    op.add_column('fights', sa.Column('processed', sa.Boolean, nullable=False, server_default=sa.false()))
    op.drop_column('fights', 'state')
