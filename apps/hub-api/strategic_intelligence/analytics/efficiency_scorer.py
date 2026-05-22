"""
Presales efficiency scoring: composite 0–100 score across win rate,
cycle time, approval velocity, bottleneck frequency, and throughput.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class EfficiencyBreakdown:
    win_rate_score: float           # 0–25
    cycle_time_score: float         # 0–20
    approval_velocity_score: float  # 0–20
    throughput_score: float         # 0–20
    bottleneck_score: float         # 0–15
    total_score: float              # 0–100


@dataclass
class PresalesEfficiencyReport:
    period_label: str
    overall_score: float
    score_label: str                # excellent | good | fair | poor
    breakdown: EfficiencyBreakdown
    win_rate: float
    avg_cycle_days: float
    proposals_per_sme_per_month: float
    avg_approval_days: float
    bottleneck_frequency: float     # bottleneck stages / total stages checked
    trend: str                      # improving | stable | declining (placeholder)
    insights: list[str]
    generated_at: str


def _score_label(score: float) -> str:
    if score >= 75:
        return "excellent"
    if score >= 55:
        return "good"
    if score >= 35:
        return "fair"
    return "poor"


def compute_efficiency_score(db: "Session", period_label: str = "current") -> PresalesEfficiencyReport:
    from sqlalchemy import select
    from models import Proposal, Approval
    from models.stakeholder import Stakeholder

    now = datetime.now(timezone.utc)
    proposals = db.scalars(select(Proposal)).all()
    approvals = db.scalars(select(Approval)).all()
    stakeholders = db.scalars(select(Stakeholder)).all()

    n = len(proposals)
    n_smes = max(len(stakeholders), 1)

    # Win rate (0–25 points)
    won = sum(1 for p in proposals if p.stage == "closed_won")
    lost = sum(1 for p in proposals if p.stage == "closed_lost")
    total_closed = won + lost
    win_rate = won / total_closed if total_closed else 0.0
    win_rate_score = min(25, win_rate * 25 / 0.60)  # 60% win rate = full score

    # Cycle time (0–20 points): avg days from intake to closed
    cycle_days_list = []
    for p in proposals:
        if p.stage in ("closed_won", "closed_lost") and p.created_at and p.submitted_at:
            created = p.created_at.replace(tzinfo=timezone.utc) if p.created_at.tzinfo is None else p.created_at
            submitted = p.submitted_at.replace(tzinfo=timezone.utc) if p.submitted_at.tzinfo is None else p.submitted_at
            cycle_days_list.append((submitted - created).days)
    avg_cycle = sum(cycle_days_list) / len(cycle_days_list) if cycle_days_list else 0.0
    # Target: 30 days = full score, 90+ days = 0
    cycle_time_score = max(0, min(20, (90 - avg_cycle) / 60 * 20)) if avg_cycle > 0 else 10.0

    # Approval velocity (0–20 points): ratio of decided to total approvals
    total_appr = len(approvals)
    decided = sum(1 for a in approvals if a.status in ("approved", "rejected"))
    velocity = decided / total_appr if total_appr else 1.0
    approval_velocity_score = velocity * 20

    # Average approval days
    appr_days = []
    for a in approvals:
        if a.created_at and a.decided_at:
            c = a.created_at.replace(tzinfo=timezone.utc) if a.created_at.tzinfo is None else a.created_at
            d = a.decided_at.replace(tzinfo=timezone.utc) if a.decided_at.tzinfo is None else a.decided_at
            appr_days.append((d - c).days)
    avg_appr_days = sum(appr_days) / len(appr_days) if appr_days else 0.0

    # Throughput score (0–20 points): proposals per SME per month
    # Target: 0.5 proposals/SME/month = full score
    proposals_per_sme_month = (n / n_smes) / 12  # annualized
    throughput_score = min(20, proposals_per_sme_month / 0.5 * 20)

    # Bottleneck frequency (0–15 points): fraction of review stages without bottlenecks
    review_stages = {
        "technical_review", "security_review", "delivery_review",
        "finance_review", "legal_review", "approval",
    }
    stage_counts: dict[str, int] = {}
    for a in approvals:
        if a.status == "pending" and a.stage in review_stages:
            stage_counts[a.stage] = stage_counts.get(a.stage, 0) + 1

    bottleneck_stages = sum(1 for count in stage_counts.values() if count >= 3)
    bottleneck_freq = bottleneck_stages / len(review_stages)
    bottleneck_score = max(0, (1 - bottleneck_freq) * 15)

    total = win_rate_score + cycle_time_score + approval_velocity_score + throughput_score + bottleneck_score

    breakdown = EfficiencyBreakdown(
        win_rate_score=round(win_rate_score, 2),
        cycle_time_score=round(cycle_time_score, 2),
        approval_velocity_score=round(approval_velocity_score, 2),
        throughput_score=round(throughput_score, 2),
        bottleneck_score=round(bottleneck_score, 2),
        total_score=round(total, 2),
    )

    insights: list[str] = []
    if win_rate < 0.40:
        insights.append(f"Win rate {win_rate:.0%} — below 40% target. Review qualification criteria.")
    if avg_cycle > 60:
        insights.append(f"Avg cycle {avg_cycle:.0f} days — above 60-day target. Identify stage dwell points.")
    if velocity < 0.70:
        insights.append(f"Approval velocity {velocity:.0%} — many approvals still pending.")
    if bottleneck_stages >= 2:
        insights.append(f"{bottleneck_stages} review stage(s) showing bottleneck patterns.")
    if not insights:
        insights.append("All efficiency indicators within target range.")

    return PresalesEfficiencyReport(
        period_label=period_label,
        overall_score=round(total, 2),
        score_label=_score_label(total),
        breakdown=breakdown,
        win_rate=round(win_rate, 3),
        avg_cycle_days=round(avg_cycle, 1),
        proposals_per_sme_per_month=round(proposals_per_sme_month, 3),
        avg_approval_days=round(avg_appr_days, 1),
        bottleneck_frequency=round(bottleneck_freq, 3),
        trend="stable",
        insights=insights,
        generated_at=now.isoformat(),
    )
