"""SQLAlchemy models for persisting strategic intelligence outputs."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class ForecastSnapshot(Base):
    __tablename__ = "forecast_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    period_label: Mapped[str] = mapped_column(String(50))  # e.g. "Q2-2026", "rolling-30d"
    total_pipeline_cr: Mapped[float] = mapped_column(Float, default=0.0)
    weighted_forecast_cr: Mapped[float] = mapped_column(Float, default=0.0)
    forecast_low_cr: Mapped[float] = mapped_column(Float, default=0.0)
    forecast_high_cr: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    pipeline_health_score: Mapped[int] = mapped_column(Integer, default=0)
    stage_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    active_proposals: Mapped[int] = mapped_column(Integer, default=0)
    at_risk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CapacitySnapshot(Base):
    __tablename__ = "capacity_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    overloaded_smes: Mapped[int] = mapped_column(Integer, default=0)
    at_risk_smes: Mapped[int] = mapped_column(Integer, default=0)
    total_smes: Mapped[int] = mapped_column(Integer, default=0)
    saturation_pct: Mapped[float] = mapped_column(Float, default=0.0)
    pending_approvals: Mapped[int] = mapped_column(Integer, default=0)
    bottleneck_stages: Mapped[list] = mapped_column(JSON, default=list)
    sme_details: Mapped[list] = mapped_column(JSON, default=list)
    burnout_risk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EscalationPrediction(Base):
    __tablename__ = "escalation_predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    proposal_id: Mapped[str] = mapped_column(String(36), index=True)
    escalation_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(20))  # low | medium | high | critical
    contributing_factors: Mapped[list] = mapped_column(JSON, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EfficiencyScore(Base):
    __tablename__ = "efficiency_scores"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    period_label: Mapped[str] = mapped_column(String(50))
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_cycle_days: Mapped[float] = mapped_column(Float, default=0.0)
    proposals_per_sme: Mapped[float] = mapped_column(Float, default=0.0)
    approval_velocity: Mapped[float] = mapped_column(Float, default=0.0)
    bottleneck_frequency: Mapped[float] = mapped_column(Float, default=0.0)
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class StrategyRecommendation(Base):
    __tablename__ = "strategy_recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    category: Mapped[str] = mapped_column(String(50))  # staffing|escalation|workflow|prioritization
    priority: Mapped[str] = mapped_column(String(20))  # critical|high|medium|low
    title: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text, default="")
    impact: Mapped[str] = mapped_column(Text, default="")
    action_items: Mapped[list] = mapped_column(JSON, default=list)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    acknowledged: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
