"""add account lockout fields to users

Revision ID: h4i5j6k7l8m9
Revises: g3h4i5j6k7l8
Create Date: 2026-05-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "h4i5j6k7l8m9"
down_revision = "g3h4i5j6k7l8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_count")
