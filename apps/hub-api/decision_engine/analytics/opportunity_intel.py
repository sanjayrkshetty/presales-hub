"""
Opportunity Intelligence.

Aggregates signals across an opportunity's full lifecycle to produce an
intelligence summary: win likelihood, urgency, recommended actions.

This is a read-only view layer — no writes.  All persistence is handled
by the caller (router or Temporal activity).
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional

from decision_engine.scoring.deal_risk import compute_deal_risk, DealRiskScore


@dataclass
class OpportunityIntelligence:
    opportunity_id: str
    title: str
    deal_risk: DealRiskScore
    health_score: int               # latest proposal health score
    health_classification: str      # green/yellow/orange/red
    stage: str
    win_probability: int
    days_to_deadline: Optional[int]
    urgent: bool
    recommended_actions: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "opportunity_id": self.opportunity_id,
            "title": self.title,
            "deal_risk": self.deal_risk.to_dict(),
            "health_score": self.health_score,
            "health_classification": self.health_classification,
            "stage": self.stage,
            "win_probability": self.win_probability,
            "days_to_deadline": self.days_to_deadline,
            "urgent": self.urgent,
            "recommended_actions": self.recommended_actions,
            "generated_at": self.generated_at,
        }


def _days_to_deadline(deadline: Optional[date]) -> Optional[int]:
    if not deadline:
        return None
    return (deadline - datetime.utcnow().date()).days


def _is_urgent(days: Optional[int], risk_level: str) -> bool:
    if risk_level in {"critical", "high"}:
        return True
    if days is not None and days <= 14:
        return True
    return False


def build_opportunity_intelligence(
    opportunity,            # Opportunity ORM object
    proposal,               # Proposal ORM object (may be None)
    pending_approvals: int,
    total_approvals: int,
) -> OpportunityIntelligence:
    """
    Build an OpportunityIntelligence view.
    All ORM objects must already be loaded — no lazy loading called here.
    """
    deadline = getattr(opportunity, "deadline", None)
    created_at = getattr(opportunity, "created_at", None)
    days = _days_to_deadline(deadline)

    deal_risk = compute_deal_risk(
        opportunity_id=opportunity.id,
        stage=opportunity.stage,
        win_probability=getattr(opportunity, "win_probability", 50),
        deal_value_cr=float(opportunity.deal_value_cr) if opportunity.deal_value_cr else None,
        deadline=deadline,
        created_at=created_at,
        pending_approvals=pending_approvals,
        total_approvals=total_approvals,
    )

    health_score = 0
    health_class = "red"
    if proposal:
        health_score = getattr(proposal, "health_score", 0) or 0
        if health_score >= 80:
            health_class = "green"
        elif health_score >= 60:
            health_class = "yellow"
        elif health_score >= 40:
            health_class = "orange"

    urgent = _is_urgent(days, deal_risk.risk_level)

    actions: list[str] = list(deal_risk.recommendations)
    if health_score < 60 and proposal:
        actions.append("Improve proposal completeness before next review")
    if urgent and not actions:
        actions.append("Review immediately — deadline within 2 weeks")

    return OpportunityIntelligence(
        opportunity_id=opportunity.id,
        title=opportunity.title,
        deal_risk=deal_risk,
        health_score=health_score,
        health_classification=health_class,
        stage=opportunity.stage,
        win_probability=getattr(opportunity, "win_probability", 50),
        days_to_deadline=days,
        urgent=urgent,
        recommended_actions=actions,
    )
