"""Add uploaded_by to fights

Revision ID: 7f3c2a9d1e04
Revises: b5c6d7e8f9a0
Create Date: 2026-10-05 00:00:00.000000

Records which signed-in user uploaded the fight, so the backend can email them
when the pipeline finishes it (backend/app/services/notification_service.py).

Written once, by POST /fights/upload. The pipeline never writes it, so its
fights upsert must not add it to the ON CONFLICT ... DO UPDATE list. NULL means
unknown: fights uploaded before this column existed, and fights the pipeline
registers itself (batch and single-file mode).

ON DELETE SET NULL matches the fighter FKs. Users are disabled, never deleted,
so it should not fire.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7f3c2a9d1e04'
down_revision: Union[str, Sequence[str], None] = 'b5c6d7e8f9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fights', sa.Column('uploaded_by', sa.Integer, nullable=True))
    op.create_foreign_key(
        'fk_fights_uploaded_by', 'fights', 'users',
        ['uploaded_by'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_fights_uploaded_by', 'fights', type_='foreignkey')
    op.drop_column('fights', 'uploaded_by')
