"""
Executive intelligence: operational summaries, pipeline risk, quarter reports,
staffing recommendations, SLA risk, delivery readiness.

Outputs are structured, narrative-free where possible — tables over prose.
Language avoids certainty: uses "projected", "estimated", "indicative".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class ExecutiveSummary:
    generated_at: str
    headline_metrics: dict              # KPIs at a glance
    pipeline_snapshot: dict
    capacity_snapshot: dict
    escalation_snapshot: dict
    quarter_projection: dict
    top_risks: list[dict]               # top 5 risks with severity + action
    top_recommendations: list[dict]     # top 5 recommendations
    economics_snapshot: dict
    delivery_readiness: str             # on_track | at_risk | critical
    delivery_rationale: str
    confidence: float
    period_label: str


def generate_executive_summary(db: "Session", period_label: str = "current") -> ExecutiveSummary:
    from strategic_intelligence.forecasting.pipeline_forecast import compute_pipeline_forecast
    from strategic_intelligence.forecasting.quarter_projection import compute_quarter_projection
    from strategic_intelligence.capacity.team_capacity import compute_capacity_report
    from strategic_intelligence.prediction.escalation_predictor import predict_escalations
    from strategic_intelligence.economics.cost_tracker import compute_organizational_economics
    from strategic_intelligence.recommendations.recommendation_engine import generate_recommendations

    now = datetime.now(timezone.utc)

    forecast = compute_pipeline_forecast(db, period_label=period_label)
    quarter = compute_quarter_projection(db)
    capacity = compute_capacity_report(db)
    escalations = predict_escalations(db)
    economics = compute_organizational_economics(db, period_label=period_label)
    recs = generate_recommendations(db)

    # Headline KPIs
    headline = {
        "total_pipeline_cr": forecast.total_pipeline_cr,
        "weighted_forecast_cr": forecast.weighted_forecast_cr,
        "forecast_range": f"{forecast.forecast_low_cr:.2f}–{forecast.forecast_high_cr:.2f} Cr",
        "pipeline_health": forecast.pipeline_health_label,
        "active_proposals": forecast.active_proposals,
        "at_risk_proposals": forecast.at_risk_count,
        "overloaded_smes": capacity.overloaded_smes,
        "pending_approvals": capacity.pending_approvals,
        "high_escalation_risk": escalations.high_risk_count,
        "quarter_projected_close_cr": quarter.projected_close_cr,
        "closed_won_cr_ytd": forecast.closed_won_cr,
    }

    pipeline_snapshot = {
        "health": forecast.pipeline_health_label,
        "health_score": forecast.pipeline_health_score,
        "weighted_forecast_cr": forecast.weighted_forecast_cr,
        "confidence": forecast.confidence,
        "contributing_factors": forecast.contributing_factors,
        "stage_summary": [
            {"stage": s.stage, "count": s.proposal_count, "weighted_cr": s.weighted_value_cr}
            for s in forecast.stage_breakdown[:6]
        ],
    }

    capacity_snapshot = {
        "overall": capacity.overall_capacity_label,
        "saturation_pct": capacity.saturation_pct,
        "overloaded": capacity.overloaded_smes,
        "at_risk": capacity.at_risk_smes,
        "burnout_risk": capacity.burnout_risk_count,
        "bottleneck_count": len(capacity.bottleneck_stages),
        "throughput_risk": capacity.throughput_risk,
        "top_bottlenecks": [
            {"stage": b.stage, "pending": b.pending_count, "severity": b.severity}
            for b in capacity.bottleneck_stages[:3]
        ],
    }

    escalation_snapshot = {
        "assessed": escalations.assessed_proposals,
        "high_risk": escalations.high_risk_count,
        "medium_risk": escalations.medium_risk_count,
        "top_escalations": [
            {
                "proposal_id": s.proposal_id,
                "score": s.escalation_score,
                "risk_level": s.risk_level,
                "top_factor": s.contributing_factors[0] if s.contributing_factors else None,
                "value_cr": s.deal_value_cr,
            }
            for s in escalations.signals[:3]
        ],
    }

    quarter_projection = {
        "label": quarter.quarter_label,
        "projected_close_cr": quarter.projected_close_cr,
        "best_case_cr": quarter.best_case_cr,
        "worst_case_cr": quarter.worst_case_cr,
        "proposals_due": quarter.proposals_due,
        "on_track": quarter.proposals_on_track,
        "at_risk": quarter.proposals_at_risk,
        "confidence": quarter.confidence,
    }

    economics_snapshot = {
        "total_cost_cr": economics.total_estimated_cost_cr,
        "avg_cost_per_proposal_cr": economics.avg_cost_per_proposal_cr,
        "pipeline_efficiency_pct": economics.pipeline_efficiency_score,
        "avg_approval_latency_days": economics.avg_approval_latency_days,
        "revenue_per_sme_cr": economics.revenue_per_sme_cr,
        "pipeline_roi": economics.pipeline_roi,
        "key_insights": economics.insights[:3],
    }

    # Top risks: assemble from all sources
    top_risks: list[dict] = []
    for sig in escalations.signals[:2]:
        if sig.risk_level in ("high", "critical"):
            top_risks.append({
                "source": "escalation",
                "severity": sig.risk_level,
                "description": f"Proposal {sig.proposal_id[:8]} — {sig.contributing_factors[0] if sig.contributing_factors else 'escalation risk'}",
                "value_at_risk_cr": sig.deal_value_cr,
                "action": sig.recommended_action,
            })
    for b in capacity.bottleneck_stages[:2]:
        if b.severity in ("high", "critical"):
            top_risks.append({
                "source": "capacity",
                "severity": b.severity,
                "description": b.rationale,
                "value_at_risk_cr": None,
                "action": f"Expedite '{b.stage}' approvals",
            })
    if forecast.pipeline_health_label == "red":
        top_risks.append({
            "source": "pipeline",
            "severity": "high",
            "description": "Pipeline health in red zone — forecast confidence low",
            "value_at_risk_cr": forecast.total_pipeline_cr,
            "action": "Convene pipeline review",
        })
    top_risks = top_risks[:5]

    # Top recommendations
    top_recs = [
        {
            "category": r.category,
            "priority": r.priority,
            "title": r.title,
            "impact": r.impact,
            "top_action": r.action_items[0] if r.action_items else "",
        }
        for r in recs.recommendations[:5]
    ]

    # Delivery readiness
    if capacity.overall_capacity_label == "critical" or escalations.high_risk_count >= 3:
        delivery_readiness = "critical"
        delivery_rationale = f"Critical capacity issues ({capacity.overloaded_smes} overloaded SMEs) and {escalations.high_risk_count} high-risk escalations."
    elif capacity.overall_capacity_label == "strained" or escalations.high_risk_count >= 1:
        delivery_readiness = "at_risk"
        delivery_rationale = f"Strained capacity ({capacity.saturation_pct:.0%} saturation) with {escalations.high_risk_count} high escalation risk proposal(s)."
    else:
        delivery_readiness = "on_track"
        delivery_rationale = "Capacity and risk indicators within acceptable thresholds."

    overall_confidence = (
        forecast.confidence * 0.4 +
        quarter.confidence * 0.3 +
        min(0.9, 0.5 + escalations.assessed_proposals * 0.02) * 0.3
    )

    return ExecutiveSummary(
        generated_at=now.isoformat(),
        headline_metrics=headline,
        pipeline_snapshot=pipeline_snapshot,
        capacity_snapshot=capacity_snapshot,
        escalation_snapshot=escalation_snapshot,
        quarter_projection=quarter_projection,
        top_risks=top_risks,
        top_recommendations=top_recs,
        economics_snapshot=economics_snapshot,
        delivery_readiness=delivery_readiness,
        delivery_rationale=delivery_rationale,
        confidence=round(overall_confidence, 3),
        period_label=period_label,
    )
