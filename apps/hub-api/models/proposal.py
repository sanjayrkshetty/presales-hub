import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, JSON, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.database import Base


VALID_STAGES = [
    "intake", "qualification", "sme_assignment", "drafting",
    "technical_review", "security_review", "delivery_review",
    "finance_review", "legal_review", "approval",
    "submission", "client_followup", "closed_won", "closed_lost",
]

TRANSITIONS: dict[str, list[str]] = {
    "intake":            ["qualification"],
    "qualification":     ["sme_assignment", "closed_lost"],
    "sme_assignment":    ["drafting", "closed_lost"],
    "drafting":          ["technical_review", "security_review", "delivery_review"],
    "technical_review":  ["finance_review", "drafting"],
    "security_review":   ["finance_review", "drafting"],
    "delivery_review":   ["finance_review", "drafting"],
    "finance_review":    ["legal_review", "approval"],
    "legal_review":      ["approval"],
    "approval":          ["submission", "drafting"],
    "submission":        ["client_followup"],
    "client_followup":   ["closed_won", "closed_lost"],
    "closed_won":        [],
    "closed_lost":       [],
}

PARALLEL_REVIEW_GROUP = {"technical_review", "security_review", "delivery_review"}


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    opportunity_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("opportunities.id"))
    stage: Mapped[str] = mapped_column(Text, default="intake")
    health_score: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_proposals_stage", "stage"),
    )

    opportunity = relationship("Opportunity", back_populates="proposal")
    assignments = relationship("Assignment", back_populates="proposal", cascade="all, delete-orphan")
    approvals = relationship("Approval", back_populates="proposal", cascade="all, delete-orphan")
    activity = relationship("ActivityFeed", back_populates="proposal", cascade="all, delete-orphan")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    proposal_id: Mapped[str] = mapped_column(String(36), ForeignKey("proposals.id"))
    stakeholder_id: Mapped[str] = mapped_column(String(36), ForeignKey("stakeholders.id"))
    role: Mapped[str | None] = mapped_column(Text)
    bu: Mapped[str | None] = mapped_column(Text)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(Text, default="pending")
    notes: Mapped[str | None] = mapped_column(Text)

    proposal = relationship("Proposal", back_populates="assignments")
    stakeholder = relationship("Stakeholder", back_populates="assignments")


class SlaConfig(Base):
    __tablename__ = "sla_configs"

    stage: Mapped[str] = mapped_column(Text, primary_key=True)
    hours_allowed: Mapped[int] = mapped_column(Integer, nullable=False)
    escalate_to_role: Mapped[str | None] = mapped_column(Text)


class ActivityFeed(Base):
    __tablename__ = "activity_feed"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    proposal_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("proposals.id"))
    actor_name: Mapped[str | None] = mapped_column(Text)
    action_type: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    is_alert: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_activity_proposal", "proposal_id"),
        Index("idx_activity_created", "created_at"),
    )

    proposal = relationship("Proposal", back_populates="activity")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type: Mapped[str | None] = mapped_column(Text)
    entity_id: Mapped[str | None] = mapped_column(String(36))
    actor_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str | None] = mapped_column(Text)
    from_state: Mapped[str | None] = mapped_column(Text)
    to_state: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_audit_entity", "entity_id"),
    )
