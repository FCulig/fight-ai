"""Create users table

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-09-29 00:00:00.000000

Backs Google sign-in (backend/app/api/routes/auth.py). Every API route now
requires a session, and the session cookie holds only `users.id`. The backend
re-reads this row on every request, so changing `role` or `is_active` takes
effect immediately without touching the cookie.

Any Google account that signs in is created as `viewer`. Admins raise the role
on the Users page, or pre-provision an email before its first sign-in.
Access is revoked with `is_active = false`, never by deleting the row: with
auto-join, a deleted user would simply come back as a viewer next time.

`email` is stored lowercased (CHECK) because it is the match key between a
pre-provisioned row and the address Google returns.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b5c6d7e8f9a0'
down_revision: Union[str, Sequence[str], None] = 'a4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('email', sa.String(320), nullable=False, unique=True),
        sa.Column('name', sa.String(200), nullable=True),
        sa.Column('role', sa.String(20), nullable=False, server_default='viewer'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.TIMESTAMP, nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('last_login_at', sa.TIMESTAMP, nullable=True),
        sa.CheckConstraint('email = lower(email)', name='ck_users_email_lowercase'),
        sa.CheckConstraint("role IN ('viewer', 'labeller', 'admin')", name='ck_users_role'),
    )


def downgrade() -> None:
    op.drop_table('users')
