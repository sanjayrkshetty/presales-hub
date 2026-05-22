"""
Persistence models for the Decision Intelligence Layer.

Six tables that store scored outputs, predictions, anomalies, and timing
metrics so every AI-assisted decision is auditable and replayable.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text,
)
from sqlalchemy.orm import relationship

from db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ProposalScore(Base):
    """Snapshot of a proposal health score at a point in time."""
    __tablename__ = "proposal_scores"

    id = Column(String(36), primary_key=True, default=_uuid)
    proposal_id = Column(String(36), ForeignKey("proposals.id"), nullable=False, index=True)
    scored_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    overall_score = Column(Integer, nullable=False)
    breakdown = Column(JSON, default=dict)
    risk_factors = Column(JSON, default=list)
    missing_requirements = Column(JSON, default=list)
    readiness_classification = Column(Text, nullable=True)  # green/yellow/orange/red
    explanation = Column(Text, nullable=True)               # LLM narrative (optional)
    model_version = Column(Text, default="v1", nullable=False)
    triggered_by = Column(Text, default="manual", nullable=False)  # manual/event/temporal/api

    proposal = relationship("Proposal", backref="scores", foreign_keys=[proposal_id])


class SlaPrediction(Base):
    """Predicted SLA breach risk for a proposal at a given stage."""
    __tablename__ = "sla_predictions"

    id = Column(String(36), primary_key=True, default=_uuid)
    proposal_id = Column(String(36), ForeignKey("proposals.id"), nullable=False, index=True)
    opportunity_id = Column(String(36), ForeignKey("opportunities.id"), nullable=False)
    stage = Column(Text, nullable=False)
    predicted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    breach_probability = Column(Float, nullable=False)
    predicted_hours_to_breach = Column(Float, nullable=True)
    risk_level = Column(Text, nullable=False)   # low/medium/high/critical
    factors = Column(JSON, default=list)
    actual_breached = Column(Boolean, nullable=True)  # back-filled after resolution

    proposal = relationship("Proposal", backref="sla_predictions", foreign_keys=[proposal_id])
    opportunity = relationship("Opportunity", backref="sla_predictions", foreign_keys=[opportunity_id])


class BottleneckSnapshot(Base):
    """Point-in-time snapshot of a predicted workflow bottleneck at a stage."""
    __tablename__ = "bottleneck_snapshots"

    id = Column(String(36), primary_key=True, default=_uuid)
    captured_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    stage = Column(Text, nullable=False)
    severity = Column(Text, nullable=False)           # low/medium/high
    affected_count = Column(Integer, default=0)       # number of proposals stalled
    estimated_delay_hours = Column(Float, default=0.0)
    factors = Column(JSON, default=list)


class SmeRecommendationAudit(Base):
    """Audit log of every SME ranking event so recommendation quality can be tracked."""
    __tablename__ = "sme_recommendation_audit"

    id = Column(String(36), primary_key=True, default=_uuid)
    proposal_id = Column(String(36), ForeignKey("proposals.id"), nullable=False, index=True)
    recommended_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    rfp_type = Column(Text, nullable=True)
    ranked_candidates = Column(JSON, default=list)  # [{stakeholder_id, score, factors}]
    selected_stakeholder_id = Column(String(36), ForeignKey("stakeholders.id"), nullable=True)
    outcome = Column(Text, nullable=True)  # accepted/overridden/pending

    proposal = relationship("Proposal", backref="sme_recommendations", foreign_keys=[proposal_id])
    selected = relationship("Stakeholder", foreign_keys=[selected_stakeholder_id])


class ApprovalAnomaly(Base):
    """Detected anomaly in an approval event."""
    __tablename__ = "approval_anomalies"

    id = Column(String(36), primary_key=True, default=_uuid)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approval_id = Column(String(36), ForeignKey("approvals.id"), nullable=True)
    proposal_id = Column(String(36), ForeignKey("proposals.id"), nullable=False, index=True)
    anomaly_type = Column(Text, nullable=False)  # fast_approval/self_approval/pattern_break/bypass
    severity = Column(Text, nullable=False)       # low/medium/high
    details = Column(JSON, default=dict)
    acknowledged = Column(Boolean, default=False, nullable=False)

    proposal = relationship("Proposal", backref="anomalies", foreign_keys=[proposal_id])
    approval = relationship("Approval", backref="anomalies", foreign_keys=[approval_id])


class WorkflowTimingMetric(Base):
    """
    Records how long each proposal spent in each stage.
    Populated by the stage-transition activity; exited_at filled on the next transition.
    Used by WorkflowThroughputAnalytics to compute per-stage p50/p90 durations.
    """
    __tablename__ = "workflow_timing_metrics"

    id = Column(String(36), primary_key=True, default=_uuid)
    opportunity_id = Column(String(36), ForeignKey("opportunities.id"), nullable=False, index=True)
    proposal_id = Column(String(36), ForeignKey("proposals.id"), nullable=False, index=True)
    stage = Column(Text, nullable=False)
    entered_at = Column(DateTime, nullable=False)
    exited_at = Column(DateTime, nullable=True)
    duration_hours = Column(Float, nullable=True)  # None until exited
    sla_hours = Column(Integer, nullable=True)
    breached = Column(Boolean, default=False, nullable=False)

    opportunity = relationship("Opportunity", backref="timing_metrics", foreign_keys=[opportunity_id])
    proposal = relationship("Proposal", backref="timing_metrics", foreign_keys=[proposal_id])
