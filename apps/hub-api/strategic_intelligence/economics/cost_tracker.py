"""
Organizational economics: cost per proposal, review efficiency,
approval latency cost, revenue per SME, pipeline efficiency, ROI indicators.

All monetary values in Crore (Cr). All interpretations are advisory.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from strategic_intelligence.config import (
    APPROVAL_COST_PER_DAY_CR,
    HOURLY_RATE_CR,
    REVIEW_HOURS_PER_STAGE,
    SME_HOURS_PER_PROPOSAL,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class ProposalEconomics:
    proposal_id: str
    estimated_cost_cr: float
    review_stages_completed: int
    approval_latency_days: float
    approval_latency_cost_cr: float
    total_cost_cr: float
    deal_value_cr: float | None
    estimated_roi: float | None      # (value × win_prob − cost) / cost
    cost_efficiency: str             # good | acceptable | poor


@dataclass
class OrganizationalEconomics:
    period_label: str
    total_pipeline_value_cr: float
    total_estimated_cost_cr: float
    avg_cost_per_proposal_cr: float
    proposals_analyzed: int
    closed_won_value_cr: float
    closed_won_count: int
    revenue_per_sme_cr: float
    proposals_per_sme_per_month: float
    avg_approval_latency_days: float
    approval_latency_cost_total_cr: float
    pipeline_efficiency_score: float    # 0–100
    pipeline_roi: float | None
    proposal_details: list[ProposalEconomics]
    rationale: str
    insights: list[str]


def _estimate_review_stages(proposal) -> int:
    review_stages = {
        "technical_review", "security_review", "delivery_review",
        "finance_review", "legal_review",
    }
    from strategic_intelligence.config import STAGE_ORDER
    try:
        idx = STAGE_ORDER.index(proposal.stage)
    except ValueError:
        idx = 0
    completed = sum(
        1 for s in STAGE_ORDER[:idx + 1] if s in review_stages
    )
    return completed


def compute_organizational_economics(db: "Session", period_label: str = "current") -> OrganizationalEconomics:
    from sqlalchemy import select
    from models import Proposal, Approval
    from models.opportunity import Opportunity
    from models.stakeholder import Stakeholder

    proposals = db.scalars(select(Proposal)).all()
    approvals = db.scalars(select(Approval)).all()
    stakeholders = db.scalars(select(Stakeholder)).all()
    now = datetime.now(timezone.utc)

    opp_ids = [p.opportunity_id for p in proposals if p.opportunity_id]
    opp_map: dict[str, Opportunity] = {}
    if opp_ids:
        opps = db.scalars(select(Opportunity).where(Opportunity.id.in_(opp_ids))).all()
        opp_map = {o.id: o for o in opps}

    appr_by_proposal: dict[str, list] = {}
    for a in approvals:
        appr_by_proposal.setdefault(a.proposal_id, []).append(a)

    total_cost = 0.0
    total_pipeline = 0.0
    total_latency_cost = 0.0
    total_latency_days = 0.0
    closed_won_value = 0.0
    closed_won_count = 0
    proposal_details: list[ProposalEconomics] = []

    for p in proposals:
        opp = opp_map.get(p.opportunity_id or "")
        val = float(opp.deal_value_cr or 0) if opp else 0.0

        # Base cost: SME hours + review stage hours
        review_stages = _estimate_review_stages(p)
        base_cost = (SME_HOURS_PER_PROPOSAL + review_stages * REVIEW_HOURS_PER_STAGE) * HOURLY_RATE_CR

        # Approval latency cost: sum of days per approval × daily rate
        p_approvals = appr_by_proposal.get(p.id, [])
        latency_days = 0.0
        for a in p_approvals:
            if a.created_at and a.decided_at:
                created = a.created_at.replace(tzinfo=timezone.utc) if a.created_at.tzinfo is None else a.created_at
                decided = a.decided_at.replace(tzinfo=timezone.utc) if a.decided_at.tzinfo is None else a.decided_at
                latency_days += (decided - created).days
            elif a.created_at and a.status == "pending":
                created = a.created_at.replace(tzinfo=timezone.utc) if a.created_at.tzinfo is None else a.created_at
                latency_days += (now - created).days

        latency_cost = latency_days * APPROVAL_COST_PER_DAY_CR
        total_proposal_cost = base_cost + latency_cost

        total_cost += total_proposal_cost
        total_latency_cost += latency_cost
        total_latency_days += latency_days
        total_pipeline += val

        # ROI estimate
        win_prob = (opp.win_probability or 50) / 100.0 if opp else 0.50
        roi = ((val * win_prob) - total_proposal_cost) / total_proposal_cost if total_proposal_cost > 0 else None

        cost_eff = "good" if (roi or 0) > 5 else "acceptable" if (roi or 0) > 1 else "poor"

        if p.stage == "closed_won":
            closed_won_value += val
            closed_won_count += 1

        proposal_details.append(ProposalEconomics(
            proposal_id=p.id,
            estimated_cost_cr=round(base_cost, 4),
            review_stages_completed=review_stages,
            approval_latency_days=round(latency_days, 1),
            approval_latency_cost_cr=round(latency_cost, 4),
            total_cost_cr=round(total_proposal_cost, 4),
            deal_value_cr=val if val else None,
            estimated_roi=round(roi, 2) if roi is not None else None,
            cost_efficiency=cost_eff,
        ))

    n = len(proposals)
    avg_cost = total_cost / n if n else 0.0
    avg_latency = total_latency_days / n if n else 0.0
    n_smes = max(len(stakeholders), 1)
    revenue_per_sme = closed_won_value / n_smes
    proposals_per_sme = (n / n_smes) / max(1, 12)  # per month approximation

    # Pipeline efficiency: ratio of value to cost
    pipeline_roi = (closed_won_value - total_cost) / total_cost if total_cost > 0 else None
    efficiency_score = min(100, int((closed_won_value / max(total_pipeline, 1)) * 100))

    insights: list[str] = []
    if avg_latency > 10:
        insights.append(f"Avg approval latency {avg_latency:.1f} days — consider SLA tightening")
    if efficiency_score < 30:
        insights.append(f"Pipeline efficiency {efficiency_score}% — review conversion strategy")
    if revenue_per_sme < 1.0:
        insights.append(f"Revenue per SME {revenue_per_sme:.2f} Cr — capacity may be underutilized")
    if avg_cost > 0.5:
        insights.append(f"Avg cost per proposal {avg_cost:.4f} Cr — review process overhead")

    rationale = (
        f"Economics across {n} proposal(s). Total estimated cost: {total_cost:.3f} Cr. "
        f"Closed-won value: {closed_won_value:.3f} Cr across {closed_won_count} proposal(s). "
        f"Pipeline efficiency: {efficiency_score}%."
    )

    proposal_details.sort(key=lambda d: d.total_cost_cr, reverse=True)

    return OrganizationalEconomics(
        period_label=period_label,
        total_pipeline_value_cr=round(total_pipeline, 3),
        total_estimated_cost_cr=round(total_cost, 4),
        avg_cost_per_proposal_cr=round(avg_cost, 4),
        proposals_analyzed=n,
        closed_won_value_cr=round(closed_won_value, 3),
        closed_won_count=closed_won_count,
        revenue_per_sme_cr=round(revenue_per_sme, 3),
        proposals_per_sme_per_month=round(proposals_per_sme, 2),
        avg_approval_latency_days=round(avg_latency, 1),
        approval_latency_cost_total_cr=round(total_latency_cost, 4),
        pipeline_efficiency_score=efficiency_score,
        pipeline_roi=round(pipeline_roi, 3) if pipeline_roi is not None else None,
        proposal_details=proposal_details,
        rationale=rationale,
        insights=insights,
    )
