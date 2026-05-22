"""
Pipeline forecasting: weighted revenue, stage-probability, confidence intervals,
pipeline health scoring.

All values in Crore (Cr). Every output includes confidence + rationale.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from strategic_intelligence.config import (
    CONFIDENCE_SPREAD_FACTOR,
    PIPELINE_HEALTH_GREEN,
    PIPELINE_HEALTH_YELLOW,
    STAGE_CLOSE_WEIGHTS,
    TERMINAL_STAGES,
    WIN_STAGES,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class StageBreakdown:
    stage: str
    proposal_count: int
    total_value_cr: float
    weighted_value_cr: float
    stage_weight: float


@dataclass
class PipelineForecast:
    period_label: str
    total_pipeline_cr: float
    weighted_forecast_cr: float
    forecast_low_cr: float
    forecast_high_cr: float
    confidence: float
    pipeline_health_score: int
    pipeline_health_label: str
    stage_breakdown: list[StageBreakdown]
    active_proposals: int
    at_risk_count: int
    closed_won_cr: float
    closed_lost_cr: float
    rationale: str
    contributing_factors: list[str]


def _health_label(score: int) -> str:
    if score >= PIPELINE_HEALTH_GREEN:
        return "green"
    if score >= PIPELINE_HEALTH_YELLOW:
        return "yellow"
    return "red"


def _compute_pipeline_health(
    active: int,
    at_risk: int,
    avg_stage_weight: float,
    win_rate: float,
) -> int:
    """
    0–100 pipeline health score.
    Factors:
      - stage maturity (40): average stage weight of active proposals
      - win rate (30): historical win rate
      - at-risk ratio (30): inverse of at_risk / active
    """
    if active == 0:
        return 0

    maturity_score = min(40, int(avg_stage_weight * 40))
    win_score = min(30, int(win_rate * 30))
    at_risk_ratio = at_risk / active if active else 0
    risk_score = max(0, int((1 - at_risk_ratio) * 30))

    return maturity_score + win_score + risk_score


def compute_pipeline_forecast(
    db: "Session",
    period_label: str = "current",
    filter_stage: str | None = None,
) -> PipelineForecast:
    from sqlalchemy import select, func as sqlfunc
    from models.opportunity import Opportunity
    from models import Proposal

    proposals = db.scalars(select(Proposal)).all()
    if not proposals:
        return PipelineForecast(
            period_label=period_label,
            total_pipeline_cr=0.0,
            weighted_forecast_cr=0.0,
            forecast_low_cr=0.0,
            forecast_high_cr=0.0,
            confidence=0.0,
            pipeline_health_score=0,
            pipeline_health_label="red",
            stage_breakdown=[],
            active_proposals=0,
            at_risk_count=0,
            closed_won_cr=0.0,
            closed_lost_cr=0.0,
            rationale="No proposals in pipeline.",
            contributing_factors=[],
        )

    opp_map: dict[str, Opportunity] = {}
    opp_ids = [p.opportunity_id for p in proposals if p.opportunity_id]
    if opp_ids:
        opps = db.scalars(select(Opportunity).where(Opportunity.id.in_(opp_ids))).all()
        opp_map = {o.id: o for o in opps}

    stage_buckets: dict[str, list[float]] = {}
    for p in proposals:
        stage_buckets.setdefault(p.stage, [])
        opp = opp_map.get(p.opportunity_id or "")
        val = float(opp.deal_value_cr or 0) if opp else 0.0
        stage_buckets[p.stage].append(val)

    stage_breakdowns: list[StageBreakdown] = []
    total_pipeline_cr = 0.0
    weighted_forecast_cr = 0.0
    closed_won_cr = 0.0
    closed_lost_cr = 0.0
    active_proposals = 0
    at_risk_count = 0
    weighted_values: list[float] = []
    stage_weights_active: list[float] = []

    for stage, values in stage_buckets.items():
        weight = STAGE_CLOSE_WEIGHTS.get(stage, 0.10)
        total_val = sum(values)
        weighted_val = total_val * weight

        if stage == "closed_won":
            closed_won_cr += total_val
        elif stage == "closed_lost":
            closed_lost_cr += total_val
        else:
            total_pipeline_cr += total_val
            weighted_forecast_cr += weighted_val
            active_proposals += len(values)
            if weight < 0.40:
                at_risk_count += len(values)
            stage_weights_active.append(weight)
            weighted_values.extend([v * weight for v in values])

        stage_breakdowns.append(StageBreakdown(
            stage=stage,
            proposal_count=len(values),
            total_value_cr=round(total_val, 3),
            weighted_value_cr=round(weighted_val, 3),
            stage_weight=weight,
        ))

    # Confidence interval: ±CONFIDENCE_SPREAD_FACTOR of weighted forecast
    spread = weighted_forecast_cr * CONFIDENCE_SPREAD_FACTOR
    forecast_low = max(0.0, weighted_forecast_cr - spread)
    forecast_high = weighted_forecast_cr + spread

    # Confidence: higher when more proposals are in later stages
    avg_weight = sum(stage_weights_active) / len(stage_weights_active) if stage_weights_active else 0.0
    confidence = min(0.95, 0.40 + avg_weight * 0.55)

    # Historical win rate from closed proposals
    total_closed = closed_won_cr + closed_lost_cr
    win_rate = closed_won_cr / total_closed if total_closed > 0 else 0.50

    health = _compute_pipeline_health(active_proposals, at_risk_count, avg_weight, win_rate)

    factors: list[str] = []
    if avg_weight < 0.30:
        factors.append(f"Pipeline skewed toward early stages (avg weight {avg_weight:.0%})")
    if at_risk_count > active_proposals * 0.5:
        factors.append(f"{at_risk_count}/{active_proposals} proposals in early/low-weight stages")
    if win_rate < 0.40:
        factors.append(f"Historical win rate below 40% ({win_rate:.0%})")
    if active_proposals == 0:
        factors.append("No active proposals in pipeline")

    rationale = (
        f"Weighted forecast of {weighted_forecast_cr:.2f} Cr based on {active_proposals} active proposals "
        f"across {len(stage_buckets)} stages. Average stage close-probability: {avg_weight:.0%}. "
        f"Confidence interval: [{forecast_low:.2f}, {forecast_high:.2f}] Cr."
    )

    stage_breakdowns.sort(key=lambda s: STAGE_CLOSE_WEIGHTS.get(s.stage, 0), reverse=True)

    return PipelineForecast(
        period_label=period_label,
        total_pipeline_cr=round(total_pipeline_cr, 3),
        weighted_forecast_cr=round(weighted_forecast_cr, 3),
        forecast_low_cr=round(forecast_low, 3),
        forecast_high_cr=round(forecast_high, 3),
        confidence=round(confidence, 3),
        pipeline_health_score=health,
        pipeline_health_label=_health_label(health),
        stage_breakdown=stage_breakdowns,
        active_proposals=active_proposals,
        at_risk_count=at_risk_count,
        closed_won_cr=round(closed_won_cr, 3),
        closed_lost_cr=round(closed_lost_cr, 3),
        rationale=rationale,
        contributing_factors=factors,
    )
