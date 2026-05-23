"""users and refresh_tokens tables

Revision ID: g3h4i5j6k7l8
Revises: f2e3d4c5b6a7
Create Date: 2026-05-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "g3h4i5j6k7l8"
down_revision = "f2e3d4c5b6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), server_default=""),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("roles", sa.JSON(), server_default="[]"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), server_default=sa.false()),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_table("users")
