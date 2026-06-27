"""Add red/blue corner fighter FKs to fights

Revision ID: c2d3e4f5a6b7
Revises: c1d2e3f4a5b6
Create Date: 2026-06-27 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fights', sa.Column('red_fighter_id', sa.Integer, nullable=True))
    op.add_column('fights', sa.Column('blue_fighter_id', sa.Integer, nullable=True))
    op.create_foreign_key(
        'fk_fights_red_fighter_id', 'fights', 'fighters',
        ['red_fighter_id'], ['id'], ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_fights_blue_fighter_id', 'fights', 'fighters',
        ['blue_fighter_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_fights_blue_fighter_id', 'fights', type_='foreignkey')
    op.drop_constraint('fk_fights_red_fighter_id', 'fights', type_='foreignkey')
    op.drop_column('fights', 'blue_fighter_id')
    op.drop_column('fights', 'red_fighter_id')
