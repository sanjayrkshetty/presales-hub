"""
Quarter-close and rolling window projections.

Projects which proposals are likely to close in the current quarter and
produces a rolling N-day forecast window.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from strategic_intelligence.config import (
    FORECAST_QUARTER_DAYS,
    FORECAST_ROLLING_DAYS,
    STAGE_CLOSE_WEIGHTS,
    TERMINAL_STAGES,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class QuarterProjection:
    quarter_label: str
    quarter_start: str
    quarter_end: str
    projected_close_cr: float
    best_case_cr: float
    worst_case_cr: float
    proposals_due: int
    proposals_on_track: int
    proposals_at_risk: int
    confidence: float
    rationale: str
    stage_velocity: dict[str, float]  # stage → avg days to advance (estimated)


@dataclass
class RollingForecast:
    window_days: int
    window_label: str
    new_proposals_expected: float  # avg inflow rate × window
    expected_closures: int
    expected_revenue_cr: float
    avg_inflow_rate_per_day: float
    avg_close_rate_per_day: float
    confidence: float
    rationale: str


def _current_quarter_bounds(today: date) -> tuple[date, date]:
    q = (today.month - 1) // 3
    q_start = date(today.year, q * 3 + 1, 1)
    if q == 3:
        q_end = date(today.year, 12, 31)
    else:
        q_end = date(today.year, (q + 1) * 3 + 1, 1) - timedelta(days=1)
    return q_start, q_end


def _quarter_label(today: date) -> str:
    q = (today.month - 1) // 3 + 1
    return f"Q{q}-{today.year}"


def compute_quarter_projection(db: "Session") -> QuarterProjection:
    from sqlalchemy import select
    from models import Proposal
    from models.opportunity import Opportunity

    today = date.today()
    q_start, q_end = _current_quarter_bounds(today)

    all_proposals = db.scalars(select(Proposal)).all()
    opp_ids = [p.opportunity_id for p in all_proposals if p.opportunity_id]
    opp_map: dict[str, Opportunity] = {}
    if opp_ids:
        opps = db.scalars(select(Opportunity).where(Opportunity.id.in_(opp_ids))).all()
        opp_map = {o.id: o for o in opps}

    # Proposals with deadline in current quarter
    due_this_quarter = [
        p for p in all_proposals
        if p.opportunity_id and
        opp_map.get(p.opportunity_id) and
        opp_map[p.opportunity_id].deadline and
        q_start <= opp_map[p.opportunity_id].deadline <= q_end and
        p.stage not in TERMINAL_STAGES
    ]

    projected_cr = 0.0
    best_cr = 0.0
    worst_cr = 0.0
    on_track = 0
    at_risk = 0

    for p in due_this_quarter:
        opp = opp_map.get(p.opportunity_id or "")
        val = float(opp.deal_value_cr or 0) if opp else 0.0
        weight = STAGE_CLOSE_WEIGHTS.get(p.stage, 0.10)
        days_left = (q_end - today).days

        # On-track: ≥approval stage or weight ≥ 0.60 with enough time
        is_on_track = weight >= 0.55 or (weight >= 0.40 and days_left >= 21)
        if is_on_track:
            on_track += 1
            projected_cr += val * weight
            best_cr += val * min(weight * 1.25, 1.0)
            worst_cr += val * max(weight * 0.60, 0.0)
        else:
            at_risk += 1
            projected_cr += val * weight * 0.5
            worst_cr += 0.0

    # Estimate stage velocity (days per stage advance) — heuristic
    stage_velocity = {
        "intake": 3.0, "qualification": 5.0, "sme_assignment": 4.0,
        "drafting": 10.0, "technical_review": 5.0, "security_review": 5.0,
        "delivery_review": 5.0, "finance_review": 4.0, "legal_review": 4.0,
        "approval": 3.0, "submission": 2.0, "client_followup": 7.0,
    }

    confidence = 0.50
    if len(due_this_quarter) > 0:
        on_track_ratio = on_track / len(due_this_quarter)
        confidence = min(0.90, 0.40 + on_track_ratio * 0.50)

    rationale = (
        f"{len(due_this_quarter)} proposals due in {_quarter_label(today)}. "
        f"{on_track} on track, {at_risk} at risk. "
        f"Projected close: {projected_cr:.2f} Cr "
        f"[{worst_cr:.2f}–{best_cr:.2f} Cr range]."
    )

    return QuarterProjection(
        quarter_label=_quarter_label(today),
        quarter_start=q_start.isoformat(),
        quarter_end=q_end.isoformat(),
        projected_close_cr=round(projected_cr, 3),
        best_case_cr=round(best_cr, 3),
        worst_case_cr=round(worst_cr, 3),
        proposals_due=len(due_this_quarter),
        proposals_on_track=on_track,
        proposals_at_risk=at_risk,
        confidence=round(confidence, 3),
        rationale=rationale,
        stage_velocity=stage_velocity,
    )


def compute_rolling_forecast(db: "Session", window_days: int = FORECAST_ROLLING_DAYS) -> RollingForecast:
    from sqlalchemy import select
    from models import Proposal

    today = datetime.now(timezone.utc)
    cutoff = today - timedelta(days=window_days * 2)  # look back 2× window to estimate rates

    all_proposals = db.scalars(select(Proposal)).all()
    lookback = [
        p for p in all_proposals
        if p.created_at and (
            p.created_at.replace(tzinfo=timezone.utc) if p.created_at.tzinfo is None else p.created_at
        ) >= cutoff
    ]

    inflow_rate = len(lookback) / (window_days * 2) if lookback else 0.0

    closed = [p for p in lookback if p.stage == "closed_won"]
    close_rate = len(closed) / (window_days * 2) if closed else 0.0

    expected_closures = round(close_rate * window_days)

    from models.opportunity import Opportunity
    from sqlalchemy import select as sel
    opp_ids = [p.opportunity_id for p in closed if p.opportunity_id]
    opp_map = {}
    if opp_ids:
        opps = db.scalars(sel(Opportunity).where(Opportunity.id.in_(opp_ids))).all()
        opp_map = {o.id: o for o in opps}

    avg_deal = 0.0
    if closed:
        vals = [float(opp_map.get(p.opportunity_id or "", type("", (), {"deal_value_cr": 0})).deal_value_cr or 0) for p in closed]
        avg_deal = sum(vals) / len(vals) if vals else 0.0

    expected_revenue = avg_deal * expected_closures

    confidence = min(0.80, 0.30 + min(len(lookback), 20) / 25)

    rationale = (
        f"Rolling {window_days}-day window. Inflow rate: {inflow_rate:.2f}/day. "
        f"Close rate: {close_rate:.2f}/day. "
        f"Expected {expected_closures} closures, ~{expected_revenue:.2f} Cr revenue."
    )

    return RollingForecast(
        window_days=window_days,
        window_label=f"rolling-{window_days}d",
        new_proposals_expected=round(inflow_rate * window_days, 1),
        expected_closures=expected_closures,
        expected_revenue_cr=round(expected_revenue, 3),
        avg_inflow_rate_per_day=round(inflow_rate, 4),
        avg_close_rate_per_day=round(close_rate, 4),
        confidence=round(confidence, 3),
        rationale=rationale,
    )
