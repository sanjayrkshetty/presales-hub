"""Add Decision Intelligence tables.

Revision ID: e1f2a3b4c5d6
Revises: d3e4f5a6b7c8
Create Date: 2026-05-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "e1f2a3b4c5d6"
down_revision = "d3e4f5a6b7c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proposal_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("scored_at", sa.DateTime, nullable=False),
        sa.Column("overall_score", sa.Integer, nullable=False),
        sa.Column("breakdown", sa.JSON, nullable=True),
        sa.Column("risk_factors", sa.JSON, nullable=True),
        sa.Column("missing_requirements", sa.JSON, nullable=True),
        sa.Column("readiness_classification", sa.Text, nullable=True),
        sa.Column("explanation", sa.Text, nullable=True),
        sa.Column("model_version", sa.Text, nullable=False, server_default="v1"),
        sa.Column("triggered_by", sa.Text, nullable=False, server_default="manual"),
    )
    op.create_index("idx_proposal_scores_proposal", "proposal_scores", ["proposal_id"])
    op.create_index("idx_proposal_scores_scored_at", "proposal_scores", ["scored_at"])

    op.create_table(
        "sla_predictions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("opportunity_id", sa.String(36), sa.ForeignKey("opportunities.id"), nullable=False),
        sa.Column("stage", sa.Text, nullable=False),
        sa.Column("predicted_at", sa.DateTime, nullable=False),
        sa.Column("breach_probability", sa.Float, nullable=False),
        sa.Column("predicted_hours_to_breach", sa.Float, nullable=True),
        sa.Column("risk_level", sa.Text, nullable=False),
        sa.Column("factors", sa.JSON, nullable=True),
        sa.Column("actual_breached", sa.Boolean, nullable=True),
    )
    op.create_index("idx_sla_predictions_proposal", "sla_predictions", ["proposal_id"])

    op.create_table(
        "bottleneck_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("captured_at", sa.DateTime, nullable=False),
        sa.Column("stage", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False),
        sa.Column("affected_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("estimated_delay_hours", sa.Float, nullable=False, server_default="0"),
        sa.Column("factors", sa.JSON, nullable=True),
    )

    op.create_table(
        "sme_recommendation_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("recommended_at", sa.DateTime, nullable=False),
        sa.Column("rfp_type", sa.Text, nullable=True),
        sa.Column("ranked_candidates", sa.JSON, nullable=True),
        sa.Column("selected_stakeholder_id", sa.String(36), sa.ForeignKey("stakeholders.id"), nullable=True),
        sa.Column("outcome", sa.Text, nullable=True),
    )
    op.create_index("idx_sme_rec_proposal", "sme_recommendation_audit", ["proposal_id"])

    op.create_table(
        "approval_anomalies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("detected_at", sa.DateTime, nullable=False),
        sa.Column("approval_id", sa.String(36), sa.ForeignKey("approvals.id"), nullable=True),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("anomaly_type", sa.Text, nullable=False),
        sa.Column("severity", sa.Text, nullable=False),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("acknowledged", sa.Boolean, nullable=False, server_default="0"),
    )
    op.create_index("idx_anomalies_proposal", "approval_anomalies", ["proposal_id"])
    op.create_index("idx_anomalies_acknowledged", "approval_anomalies", ["acknowledged"])

    op.create_table(
        "workflow_timing_metrics",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("opportunity_id", sa.String(36), sa.ForeignKey("opportunities.id"), nullable=False),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("proposals.id"), nullable=False),
        sa.Column("stage", sa.Text, nullable=False),
        sa.Column("entered_at", sa.DateTime, nullable=False),
        sa.Column("exited_at", sa.DateTime, nullable=True),
        sa.Column("duration_hours", sa.Float, nullable=True),
        sa.Column("sla_hours", sa.Integer, nullable=True),
        sa.Column("breached", sa.Boolean, nullable=False, server_default="0"),
    )
    op.create_index("idx_timing_proposal", "workflow_timing_metrics", ["proposal_id"])
    op.create_index("idx_timing_opportunity", "workflow_timing_metrics", ["opportunity_id"])


def downgrade() -> None:
    op.drop_table("workflow_timing_metrics")
    op.drop_table("approval_anomalies")
    op.drop_table("sme_recommendation_audit")
    op.drop_table("bottleneck_snapshots")
    op.drop_table("sla_predictions")
    op.drop_table("proposal_scores")
