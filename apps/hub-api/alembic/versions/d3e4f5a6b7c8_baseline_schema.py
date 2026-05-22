"""baseline schema

Creates all 10 tables from the PRESALES HUB initial schema.
ORM models are the authoritative source — this migration was derived from them,
not from schema.sql (which is now documentation-only).

Revision ID: d3e4f5a6b7c8
Revises:
Create Date: 2026-05-22

"""
from alembic import op
import sqlalchemy as sa

revision = "d3e4f5a6b7c8"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Independent tables (no FKs) ───────────────────────────────────────────
    op.create_table(
        "sla_configs",
        sa.Column("stage", sa.Text(), primary_key=True, nullable=False),
        sa.Column("hours_allowed", sa.Integer(), nullable=False),
        sa.Column("escalate_to_role", sa.Text(), nullable=True),
    )

    op.create_table(
        "clients",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("sector", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("tier", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "stakeholders",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=True),
        sa.Column("bu", sa.Text(), nullable=True),
        sa.Column("expertise", sa.JSON(), nullable=False),
        sa.Column("current_workload", sa.Integer(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "sme_routing_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("rfp_type", sa.Text(), nullable=False),
        sa.Column("required_expertise", sa.Text(), nullable=False),
        sa.Column("bu", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
    )

    # ── Tables with FK dependencies ───────────────────────────────────────────
    op.create_table(
        "opportunities",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("client_id", sa.String(36), sa.ForeignKey("clients.id"), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("rfp_type", sa.Text(), nullable=True),
        sa.Column("deal_value_cr", sa.Numeric(10, 2), nullable=True),
        sa.Column("win_probability", sa.Integer(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("stakeholders.id"), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "proposals",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("opportunity_id", sa.String(36), sa.ForeignKey("opportunities.id"), nullable=True),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("health_score", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "assignments",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("stakeholder_id", sa.String(36), sa.ForeignKey("stakeholders.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=True),
        sa.Column("bu", sa.Text(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "approvals",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("approver_id", sa.String(36), sa.ForeignKey("stakeholders.id"), nullable=True),
        sa.Column("stage", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("parallel_group", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "activity_feed",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=True),
        sa.Column("actor_name", sa.Text(), nullable=True),
        sa.Column("action_type", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_alert", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=True),
        sa.Column("entity_id", sa.String(36), nullable=True),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("from_state", sa.Text(), nullable=True),
        sa.Column("to_state", sa.Text(), nullable=True),
        # Column name in DB is 'metadata'; ORM maps it to attribute 'meta'
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
    )

    # ── Indexes (mirrors schema.sql) ──────────────────────────────────────────
    op.create_index("idx_opportunities_stage", "opportunities", ["stage"])
    op.create_index("idx_proposals_stage",     "proposals",     ["stage"])
    op.create_index("idx_approvals_proposal",  "approvals",     ["proposal_id"])
    op.create_index("idx_activity_proposal",   "activity_feed", ["proposal_id"])
    op.create_index("idx_activity_created",    "activity_feed", ["created_at"])
    op.create_index("idx_audit_entity",        "audit_log",     ["entity_id"])


def downgrade() -> None:
    # Drop in reverse FK dependency order
    op.drop_index("idx_audit_entity",       table_name="audit_log")
    op.drop_index("idx_activity_created",   table_name="activity_feed")
    op.drop_index("idx_activity_proposal",  table_name="activity_feed")
    op.drop_index("idx_approvals_proposal", table_name="approvals")
    op.drop_index("idx_proposals_stage",    table_name="proposals")
    op.drop_index("idx_opportunities_stage",table_name="opportunities")

    op.drop_table("audit_log")
    op.drop_table("activity_feed")
    op.drop_table("approvals")
    op.drop_table("assignments")
    op.drop_table("proposals")
    op.drop_table("opportunities")
    op.drop_table("sme_routing_rules")
    op.drop_table("stakeholders")
    op.drop_table("clients")
    op.drop_table("sla_configs")
