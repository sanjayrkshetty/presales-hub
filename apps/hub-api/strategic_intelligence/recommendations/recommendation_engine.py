"""
Recommendation engine: generates actionable, prioritized recommendations across
staffing, escalation, workflow optimization, proposal prioritization, and resource allocation.

Recommendations are advisory only — no auto-execution.
Each recommendation includes: category, priority, rationale, impact, action items.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class Recommendation:
    category: str           # staffing | escalation | workflow | prioritization | resource
    priority: str           # critical | high | medium | low
    title: str
    rationale: str
    impact: str
    action_items: list[str]
    entity_id: str | None = None
    entity_type: str | None = None
    confidence: float = 0.70


@dataclass
class RecommendationReport:
    total_recommendations: int
    critical_count: int
    high_count: int
    recommendations: list[Recommendation]
    generated_at: str
    summary: str


def _priority_sort_key(p: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(p, 4)


def generate_recommendations(db: "Session") -> RecommendationReport:
    from strategic_intelligence.capacity.team_capacity import compute_capacity_report
    from strategic_intelligence.prediction.escalation_predictor import predict_escalations
    from strategic_intelligence.forecasting.pipeline_forecast import compute_pipeline_forecast
    from strategic_intelligence.economics.cost_tracker import compute_organizational_economics

    recs: list[Recommendation] = []
    now = datetime.now(timezone.utc)

    # ── Staffing recommendations ────────────────────────────────────────────
    capacity = compute_capacity_report(db)
    for profile in capacity.sme_profiles:
        if profile.risk_level == "overloaded":
            recs.append(Recommendation(
                category="staffing",
                priority="critical" if profile.saturation_pct >= 1.0 else "high",
                title=f"Redistribute workload from {profile.name}",
                rationale=f"{profile.name} is at {profile.saturation_pct:.0%} saturation with {profile.active_proposals} active proposals.",
                impact="Immediate workload redistribution will prevent SLA breaches and reduce escalation risk.",
                action_items=[
                    f"Identify 1–2 proposals that can be reassigned from {profile.name}",
                    f"Check BU '{profile.bu}' for available SMEs with matching expertise",
                    "Update assignment records after redistribution",
                ],
                entity_id=profile.stakeholder_id,
                entity_type="stakeholder",
                confidence=0.85,
            ))
        elif profile.burnout_risk:
            recs.append(Recommendation(
                category="staffing",
                priority="high",
                title=f"Schedule workload review for {profile.name}",
                rationale=f"Burnout risk detected — workload at {profile.saturation_pct:.0%} of saturation threshold.",
                impact="Proactive workload management reduces attrition risk and maintains proposal quality.",
                action_items=[
                    f"Schedule 1:1 workload review with {profile.name}",
                    "Identify low-priority tasks to defer or delegate",
                ],
                entity_id=profile.stakeholder_id,
                entity_type="stakeholder",
                confidence=0.75,
            ))

    # Approval bottleneck recommendations
    for bottleneck in capacity.bottleneck_stages:
        if bottleneck.severity in ("high", "critical"):
            recs.append(Recommendation(
                category="workflow",
                priority="critical" if bottleneck.severity == "critical" else "high",
                title=f"Clear '{bottleneck.stage}' approval bottleneck",
                rationale=bottleneck.rationale,
                impact=f"Unblocking {bottleneck.pending_count} approval(s) will advance proposals and reduce SLA breach probability.",
                action_items=[
                    f"Contact approver(s) in '{bottleneck.stage}' to expedite {bottleneck.overdue_count} overdue review(s)",
                    "Escalate to stage manager if no response within 24h",
                    "Consider parallel approval routing if available",
                ],
                entity_type="approval_stage",
                confidence=0.80,
            ))

    # ── Escalation recommendations ──────────────────────────────────────────
    escalations = predict_escalations(db)
    for signal in escalations.signals[:5]:  # top 5 by score
        if signal.risk_level in ("high", "critical"):
            recs.append(Recommendation(
                category="escalation",
                priority="critical" if signal.risk_level == "critical" else "high",
                title=f"Escalate proposal {signal.proposal_id[:8]} — {signal.risk_level} risk",
                rationale=signal.rationale,
                impact=f"Proactive escalation prevents deal loss. Deal value: {signal.deal_value_cr or 0:.1f} Cr.",
                action_items=[
                    signal.recommended_action,
                    "Assign senior sponsor to fast-track outstanding approvals",
                    f"Review contributing factors: {', '.join(signal.contributing_factors[:2])}",
                ],
                entity_id=signal.proposal_id,
                entity_type="proposal",
                confidence=signal.confidence,
            ))

    # ── Pipeline prioritization ─────────────────────────────────────────────
    forecast = compute_pipeline_forecast(db)
    if forecast.at_risk_count > 0 and forecast.at_risk_count > forecast.active_proposals * 0.4:
        recs.append(Recommendation(
            category="prioritization",
            priority="high",
            title=f"Prioritize {forecast.at_risk_count} early-stage proposals",
            rationale=f"{forecast.at_risk_count}/{forecast.active_proposals} proposals are in early stages (weight <40%) — pipeline skewed toward low-certainty deals.",
            impact="Advancing proposals from early to mid-stage improves weighted forecast by ~30%.",
            action_items=[
                "Identify top 3 early-stage proposals by deal value",
                "Assign SMEs to accelerate qualification and scoping",
                "Set 2-week milestones for stage advancement",
            ],
            confidence=0.72,
        ))

    if forecast.pipeline_health_label == "red":
        recs.append(Recommendation(
            category="prioritization",
            priority="critical",
            title="Pipeline health critical — immediate review required",
            rationale=f"Pipeline health score {forecast.pipeline_health_score}/100 (red zone). {', '.join(forecast.contributing_factors[:2])}.",
            impact="Without intervention, revenue forecast may miss targets by {:.0%}.".format(
                1 - forecast.confidence
            ),
            action_items=[
                "Convene pipeline review meeting within 48h",
                "Identify and fast-track top 3 deals by value",
                "Review win/loss patterns from last quarter",
            ],
            confidence=0.80,
        ))

    # ── Resource allocation ─────────────────────────────────────────────────
    economics = compute_organizational_economics(db)
    if economics.avg_approval_latency_days > 10:
        recs.append(Recommendation(
            category="resource",
            priority="medium",
            title="Reduce approval latency through process optimization",
            rationale=f"Average approval latency {economics.avg_approval_latency_days:.1f} days — above 10-day threshold.",
            impact=f"Reducing latency by 3 days would save ~{economics.approval_latency_cost_total_cr * 0.3:.4f} Cr and improve win rate.",
            action_items=[
                "Audit approval SLA configurations per stage",
                "Introduce automated reminders at 50% of SLA window",
                "Consider parallel approval for non-critical stages",
            ],
            confidence=0.75,
        ))

    if economics.pipeline_efficiency_score < 40:
        recs.append(Recommendation(
            category="workflow",
            priority="medium",
            title="Improve pipeline conversion efficiency",
            rationale=f"Pipeline efficiency {economics.pipeline_efficiency_score}% — closed-won value is low relative to total pipeline.",
            impact="Raising efficiency to 50% would add significant closed-won value per quarter.",
            action_items=[
                "Analyse win/loss rationale for last 10 proposals",
                "Invest in proposal quality at drafting stage",
                "Target high-probability deals for additional SME support",
            ],
            confidence=0.68,
        ))

    recs.sort(key=lambda r: _priority_sort_key(r.priority))

    critical_count = sum(1 for r in recs if r.priority == "critical")
    high_count = sum(1 for r in recs if r.priority == "high")

    summary = (
        f"{len(recs)} recommendation(s) generated: "
        f"{critical_count} critical, {high_count} high priority. "
        + (f"Top action: {recs[0].title}." if recs else "No immediate actions required.")
    )

    return RecommendationReport(
        total_recommendations=len(recs),
        critical_count=critical_count,
        high_count=high_count,
        recommendations=recs,
        generated_at=now.isoformat(),
        summary=summary,
    )
