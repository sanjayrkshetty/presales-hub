"""
Escalation prediction: scores each active proposal for escalation risk.

Every prediction includes confidence, rationale, and contributing factors.
No certainty language — outputs are probabilistic advisory signals.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from strategic_intelligence.config import (
    ESCALATION_HIGH_THRESHOLD,
    ESCALATION_MEDIUM_THRESHOLD,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class EscalationSignal:
    proposal_id: str
    proposal_stage: str
    escalation_score: float        # 0.0–1.0
    risk_level: str                # low | medium | high | critical
    confidence: float
    contributing_factors: list[str]
    rationale: str
    recommended_action: str
    deal_value_cr: float | None
    opportunity_title: str


@dataclass
class EscalationReport:
    assessed_proposals: int
    high_risk_count: int
    medium_risk_count: int
    signals: list[EscalationSignal]
    top_risk_proposal_id: str | None
    summary: str


def _risk_level(score: float) -> str:
    if score >= 0.80:
        return "critical"
    if score >= ESCALATION_HIGH_THRESHOLD:
        return "high"
    if score >= ESCALATION_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def _recommended_action(score: float, stage: str) -> str:
    if score >= 0.80:
        return f"Immediate escalation to senior leadership — critical risk in '{stage}' stage."
    if score >= ESCALATION_HIGH_THRESHOLD:
        return f"Escalate to BU head — high risk detected in '{stage}' stage. Review within 24h."
    if score >= ESCALATION_MEDIUM_THRESHOLD:
        return f"Flag for manager review — medium escalation risk in '{stage}' stage."
    return "Monitor standard workflow — no escalation required at this time."


def _score_proposal(
    proposal,
    opp,
    approvals: list,
    now: datetime,
) -> tuple[float, list[str]]:
    """
    Deterministic weighted escalation score.

    Factors (weights):
    - Deadline pressure (0.25): days until deadline vs. stage complexity
    - Approval stall (0.25): overdue approvals count
    - Deal value exposure (0.20): high-value deals get higher base risk
    - Stage dwell time (0.15): time stuck in current stage
    - Win probability (0.15): low win prob + late stage = escalation signal
    """
    score = 0.0
    factors: list[str] = []

    # 1. Deadline pressure (0.25)
    if opp and opp.deadline:
        days_left = (opp.deadline - now.date()).days
        if days_left < 0:
            score += 0.25
            factors.append(f"Deadline passed {abs(days_left)} day(s) ago")
        elif days_left < 7:
            score += 0.20
            factors.append(f"Deadline in {days_left} day(s) — critical window")
        elif days_left < 21:
            score += 0.12
            factors.append(f"Deadline in {days_left} days — approaching")
        elif days_left < 45:
            score += 0.05

    # 2. Approval stall (0.25)
    pending = [a for a in approvals if a.status == "pending"]
    overdue = [
        a for a in pending
        if a.due_at and a.due_at.replace(tzinfo=timezone.utc) < now
    ]
    if len(overdue) >= 3:
        score += 0.25
        factors.append(f"{len(overdue)} overdue approvals — severe stall")
    elif len(overdue) >= 1:
        score += 0.15
        factors.append(f"{len(overdue)} overdue approval(s)")
    elif len(pending) >= 3:
        score += 0.08
        factors.append(f"{len(pending)} pending approvals accumulating")

    # 3. Deal value exposure (0.20)
    val = float(opp.deal_value_cr or 0) if opp else 0.0
    if val >= 10:
        score += 0.20
        factors.append(f"High-value deal ({val:.1f} Cr) — elevated exposure")
    elif val >= 5:
        score += 0.12
        factors.append(f"Significant deal value ({val:.1f} Cr)")
    elif val >= 2:
        score += 0.06

    # 4. Stage dwell time (0.15)
    if proposal.updated_at:
        upd = proposal.updated_at
        if upd.tzinfo is None:
            upd = upd.replace(tzinfo=timezone.utc)
        dwell_days = (now - upd).days
        if dwell_days >= 14:
            score += 0.15
            factors.append(f"Stalled {dwell_days} days without stage change")
        elif dwell_days >= 7:
            score += 0.08
            factors.append(f"No stage change in {dwell_days} days")
        elif dwell_days >= 3:
            score += 0.03

    # 5. Win probability (0.15)
    if opp:
        win_prob = (opp.win_probability or 50) / 100.0
        from strategic_intelligence.config import STAGE_CLOSE_WEIGHTS
        stage_weight = STAGE_CLOSE_WEIGHTS.get(proposal.stage, 0.10)
        if win_prob < 0.30 and stage_weight >= 0.40:
            score += 0.15
            factors.append(f"Low win probability ({win_prob:.0%}) at late stage '{proposal.stage}'")
        elif win_prob < 0.40:
            score += 0.07
            factors.append(f"Below-average win probability ({win_prob:.0%})")

    return min(1.0, score), factors


def predict_escalations(db: "Session") -> EscalationReport:
    from sqlalchemy import select
    from models import Proposal, Approval
    from models.opportunity import Opportunity

    from strategic_intelligence.config import TERMINAL_STAGES

    now = datetime.now(timezone.utc)

    proposals = db.scalars(
        select(Proposal).where(Proposal.stage.not_in(list(TERMINAL_STAGES)))
    ).all()

    opp_ids = [p.opportunity_id for p in proposals if p.opportunity_id]
    opp_map: dict[str, Opportunity] = {}
    if opp_ids:
        opps = db.scalars(select(Opportunity).where(Opportunity.id.in_(opp_ids))).all()
        opp_map = {o.id: o for o in opps}

    all_approvals = db.scalars(select(Approval)).all()
    appr_by_proposal: dict[str, list[Approval]] = {}
    for a in all_approvals:
        appr_by_proposal.setdefault(a.proposal_id, []).append(a)

    signals: list[EscalationSignal] = []
    high_risk = 0
    medium_risk = 0

    for p in proposals:
        opp = opp_map.get(p.opportunity_id or "")
        approvals = appr_by_proposal.get(p.id, [])
        score, factors = _score_proposal(p, opp, approvals, now)
        risk = _risk_level(score)
        confidence = min(0.90, 0.45 + score * 0.45)

        if risk in ("high", "critical"):
            high_risk += 1
        elif risk == "medium":
            medium_risk += 1

        rationale = (
            f"Escalation score {score:.0%} ({risk}) based on "
            f"{len(factors)} risk factor(s). Confidence: {confidence:.0%}. "
            + (f"Key concern: {factors[0]}." if factors else "No significant risk factors detected.")
        )

        signals.append(EscalationSignal(
            proposal_id=p.id,
            proposal_stage=p.stage,
            escalation_score=round(score, 3),
            risk_level=risk,
            confidence=round(confidence, 3),
            contributing_factors=factors,
            rationale=rationale,
            recommended_action=_recommended_action(score, p.stage),
            deal_value_cr=float(opp.deal_value_cr) if opp and opp.deal_value_cr else None,
            opportunity_title=opp.title if opp else "(no opportunity)",
        ))

    signals.sort(key=lambda s: s.escalation_score, reverse=True)
    top_id = signals[0].proposal_id if signals else None

    summary = (
        f"Assessed {len(proposals)} active proposal(s). "
        f"{high_risk} high/critical escalation risk. "
        f"{medium_risk} medium risk. "
        + (f"Top risk: proposal {top_id}." if top_id else "")
    )

    return EscalationReport(
        assessed_proposals=len(proposals),
        high_risk_count=high_risk,
        medium_risk_count=medium_risk,
        signals=signals,
        top_risk_proposal_id=top_id,
        summary=summary,
    )
