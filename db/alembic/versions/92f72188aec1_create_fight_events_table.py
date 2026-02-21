"""Create fight events table

Revision ID: 92f72188aec1
Revises: 
Create Date: 2026-02-21 15:38:52.976644

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92f72188aec1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'fight_events',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('frame', sa.Integer, nullable=False),
        sa.Column('description', sa.String(100), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('fight_events')
