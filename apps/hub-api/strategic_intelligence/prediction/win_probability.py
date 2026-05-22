"""
Proposal win probability modeling.

Starts from opportunity.win_probability (base estimate) then adjusts using:
- proposal health score
- SLA adherence (approval velocity)
- deadline pressure
- deal value vs. historical pattern
- stage progression

Every output includes confidence + rationale + contributing factors.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from strategic_intelligence.config import WIN_PROB_FLOOR, WIN_PROB_CEIL, STAGE_CLOSE_WEIGHTS

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class WinProbabilityEstimate:
    proposal_id: str
    opportunity_id: str | None
    base_probability: float         # raw opportunity.win_probability / 100
    adjusted_probability: float     # model output
    confidence: float
    risk_level: str                 # low | medium | high | critical
    contributing_factors: list[str]
    rationale: str
    deal_value_cr: float | None
    stage: str


def _clamp(val: float) -> float:
    return max(WIN_PROB_FLOOR, min(WIN_PROB_CEIL, val))


def compute_win_probability(
    db: "Session",
    proposal_id: str,
) -> WinProbabilityEstimate:
    from sqlalchemy import select
    from models import Proposal, Approval
    from models.opportunity import Opportunity
    from models.intelligence import ProposalScore

    proposal = db.get(Proposal, proposal_id)
    if not proposal:
        return WinProbabilityEstimate(
            proposal_id=proposal_id,
            opportunity_id=None,
            base_probability=0.50,
            adjusted_probability=0.50,
            confidence=0.10,
            risk_level="high",
            contributing_factors=["Proposal not found"],
            rationale="Cannot compute — proposal not found.",
            deal_value_cr=None,
            stage="unknown",
        )

    opp = db.get(Opportunity, proposal.opportunity_id) if proposal.opportunity_id else None
    base = ((opp.win_probability or 50) / 100.0) if opp else 0.50
    adj = base
    factors: list[str] = []
    now = datetime.now(timezone.utc)

    # 1. Proposal health score adjustment (±0.15)
    score_rec = db.scalars(
        select(ProposalScore)
        .where(ProposalScore.proposal_id == proposal_id)
        .order_by(ProposalScore.scored_at.desc())
        .limit(1)
    ).first()
    if score_rec:
        health = score_rec.score or 0
        health_adj = (health - 60) / 100 * 0.15  # -0.09 to +0.06
        adj += health_adj
        if health_adj > 0.03:
            factors.append(f"Strong proposal health score ({health}/100) — positive signal")
        elif health_adj < -0.03:
            factors.append(f"Weak proposal health score ({health}/100) — negative signal")

    # 2. SLA / approval velocity adjustment (±0.12)
    approvals = db.scalars(
        select(Approval).where(Approval.proposal_id == proposal_id)
    ).all()
    overdue = [
        a for a in approvals
        if a.due_at and a.status == "pending" and
        a.due_at.replace(tzinfo=timezone.utc) < now
    ]
    decided = [a for a in approvals if a.status in ("approved", "rejected")]
    approval_velocity = len(decided) / max(len(approvals), 1)

    if len(overdue) >= 2:
        adj -= 0.12
        factors.append(f"{len(overdue)} overdue approvals — stalled workflow damages win probability")
    elif len(overdue) == 1:
        adj -= 0.06
        factors.append(f"1 overdue approval — mild delay signal")
    elif approval_velocity > 0.80:
        adj += 0.08
        factors.append(f"High approval velocity ({approval_velocity:.0%} decided) — strong execution signal")

    # 3. Stage close weight adjustment (±0.10)
    stage_weight = STAGE_CLOSE_WEIGHTS.get(proposal.stage, 0.10)
    stage_adj = (stage_weight - base) * 0.15
    adj += stage_adj
    if stage_adj > 0.03:
        factors.append(f"Advanced stage '{proposal.stage}' (close weight {stage_weight:.0%}) — stage-aligned with win")
    elif stage_adj < -0.03:
        factors.append(f"Early stage '{proposal.stage}' — significant execution risk remains")

    # 4. Deadline pressure adjustment (−0.08)
    if opp and opp.deadline:
        days_left = (opp.deadline - now.date()).days
        if days_left < 0:
            adj -= 0.10
            factors.append(f"Deadline passed — severely reduces close probability")
        elif days_left < 7:
            adj -= 0.06
            factors.append(f"Deadline in {days_left} day(s) — extreme pressure")
        elif days_left < 14:
            adj -= 0.03
            factors.append(f"Tight deadline ({days_left} days)")

    # 5. Deal value vs. base: large deals regress toward mean (±0.05)
    val = float(opp.deal_value_cr or 0) if opp else 0.0
    if val >= 10:
        adj -= 0.05
        factors.append(f"High-value deal ({val:.1f} Cr) — larger deals carry execution complexity")
    elif val < 1 and val > 0:
        adj += 0.03
        factors.append(f"Small deal ({val:.1f} Cr) — lower complexity, slightly higher close probability")

    adj = _clamp(adj)

    # Confidence: higher when more signals are available
    signal_count = len(factors)
    confidence = min(0.88, 0.40 + signal_count * 0.08)

    delta = adj - base
    if delta > 0.05:
        risk_level = "low"
    elif delta > -0.05:
        risk_level = "medium"
    elif delta > -0.15:
        risk_level = "high"
    else:
        risk_level = "critical"

    rationale = (
        f"Base probability {base:.0%} (from opportunity). "
        f"Adjusted to {adj:.0%} after {signal_count} signal(s). "
        f"Net change: {delta:+.0%}. Confidence: {confidence:.0%}."
    )

    return WinProbabilityEstimate(
        proposal_id=proposal_id,
        opportunity_id=proposal.opportunity_id,
        base_probability=round(base, 3),
        adjusted_probability=round(adj, 3),
        confidence=round(confidence, 3),
        risk_level=risk_level,
        contributing_factors=factors,
        rationale=rationale,
        deal_value_cr=val if val else None,
        stage=proposal.stage,
    )


def compute_portfolio_win_probabilities(db: "Session") -> list[WinProbabilityEstimate]:
    from sqlalchemy import select
    from models import Proposal
    from strategic_intelligence.config import TERMINAL_STAGES

    proposals = db.scalars(
        select(Proposal).where(Proposal.stage.not_in(list(TERMINAL_STAGES)))
    ).all()

    return [compute_win_probability(db, p.id) for p in proposals]
