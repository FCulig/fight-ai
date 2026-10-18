"""Create waitlist table

Revision ID: 8a4d1c7e2b90
Revises: 7f3c2a9d1e04
Create Date: 2026-10-18 00:00:00.000000

Sign-in is invite-only: Google sign-in succeeds only for an email that already
has a `users` row (added on the Users page, or bootstrapped by ADMIN_EMAILS).
Everyone else can leave an email here from the sign-in page, to be told when
the product opens to everyone.

Written by the unauthenticated POST /api/auth/waitlist, so it holds nothing
but the address. Inviting an address on the Users page deletes its row here.

`email` is stored lowercased (CHECK), matching `users.email`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8a4d1c7e2b90'
down_revision: Union[str, Sequence[str], None] = '7f3c2a9d1e04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'waitlist',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('email', sa.String(320), nullable=False, unique=True),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False,
                  server_default=sa.text('now()')),
        sa.CheckConstraint('email = lower(email)', name='ck_waitlist_email_lowercase'),
    )


def downgrade() -> None:
    op.drop_table('waitlist')
