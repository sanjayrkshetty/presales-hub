"""
What-if simulation engine.

Runs scenario analysis against a snapshot of current state.
NEVER mutates production data — all computations are read-only.

Supported scenarios:
1. sme_unavailable: What if a specific SME is unavailable?
2. approval_delayed: What if approval takes N extra hours?
3. rfp_surge: What if N new RFPs arrive simultaneously?
4. bu_overloaded: What if a BU reaches capacity saturation?
5. proposal_rejected: What if a specific proposal is rejected?
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, TYPE_CHECKING

from strategic_intelligence.config import (
    SME_SATURATION_WORKLOAD,
    STAGE_CLOSE_WEIGHTS,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

SCENARIO_TYPES = {
    "sme_unavailable",
    "approval_delayed",
    "rfp_surge",
    "bu_overloaded",
    "proposal_rejected",
}


@dataclass
class SimulationScenario:
    scenario_type: str
    parameters: dict[str, Any] = field(default_factory=dict)
    label: str = ""

    def __post_init__(self):
        if self.scenario_type not in SCENARIO_TYPES:
            raise ValueError(f"Unknown scenario type: {self.scenario_type!r}. Valid: {sorted(SCENARIO_TYPES)}")
        if not self.label:
            self.label = self.scenario_type.replace("_", " ").title()


@dataclass
class SimulationImpact:
    affected_proposals: int
    revenue_at_risk_cr: float
    sla_risk_increase: float        # delta probability (0–1)
    capacity_impact: str            # none | mild | moderate | severe
    escalation_risk_increase: float
    timeline_delay_days: float
    summary: str
    factors: list[str]
    confidence: float


@dataclass
class SimulationResult:
    scenario_type: str
    scenario_label: str
    parameters: dict
    impact: SimulationImpact
    current_state_snapshot: dict
    projected_state: dict
    recommendations: list[str]
    simulated_at: str
    note: str = "Simulation only — no production data was modified."


def _snapshot_current_state(db: "Session") -> dict:
    from sqlalchemy import select
    from models import Proposal, Approval
    from models.stakeholder import Stakeholder
    from models.opportunity import Opportunity

    from strategic_intelligence.config import TERMINAL_STAGES

    active_proposals = db.scalars(
        select(Proposal).where(Proposal.stage.not_in(list(TERMINAL_STAGES)))
    ).all()
    pending_approvals_count = len(db.scalars(
        select(Approval).where(Approval.status == "pending")
    ).all())
    stakeholders = db.scalars(select(Stakeholder)).all()
    opp_ids = [p.opportunity_id for p in active_proposals if p.opportunity_id]
    total_pipeline = 0.0
    if opp_ids:
        opps = db.scalars(select(Opportunity).where(Opportunity.id.in_(opp_ids))).all()
        total_pipeline = sum(float(o.deal_value_cr or 0) for o in opps)

    return {
        "active_proposals": len(active_proposals),
        "pending_approvals": pending_approvals_count,
        "total_smes": len(stakeholders),
        "avg_workload": sum(s.current_workload or 0 for s in stakeholders) / max(len(stakeholders), 1),
        "total_pipeline_cr": round(total_pipeline, 3),
    }


def _simulate_sme_unavailable(db: "Session", params: dict, snapshot: dict) -> SimulationImpact:
    from sqlalchemy import select
    from models.proposal import Assignment
    from models.stakeholder import Stakeholder
    from models.opportunity import Opportunity
    from models import Proposal

    sme_id = params.get("stakeholder_id", "")
    duration_days = int(params.get("duration_days", 5))

    s = db.get(Stakeholder, sme_id) if sme_id else None
    sme_name = s.name if s else "specified SME"

    assignments = db.scalars(
        select(Assignment).where(Assignment.stakeholder_id == sme_id)
    ).all() if sme_id else []

    affected = len(assignments)
    opp_ids = []
    for a in assignments:
        p = db.get(Proposal, a.proposal_id)
        if p and p.opportunity_id:
            opp_ids.append(p.opportunity_id)

    revenue_at_risk = 0.0
    if opp_ids:
        opps = db.scalars(select(Opportunity).where(Opportunity.id.in_(opp_ids))).all()
        revenue_at_risk = sum(float(o.deal_value_cr or 0) for o in opps)

    capacity_impact = "mild" if affected <= 2 else "moderate" if affected <= 5 else "severe"

    factors = [
        f"{sme_name} assigned to {affected} proposal(s)",
        f"Unavailability period: {duration_days} day(s)",
        f"Revenue at risk: {revenue_at_risk:.2f} Cr",
    ]
    if affected > 3:
        factors.append(f"No backup assignee modeled — redistribution required for {affected} proposals")

    return SimulationImpact(
        affected_proposals=affected,
        revenue_at_risk_cr=round(revenue_at_risk, 3),
        sla_risk_increase=min(0.4, affected * 0.06 + duration_days * 0.02),
        capacity_impact=capacity_impact,
        escalation_risk_increase=min(0.35, affected * 0.05),
        timeline_delay_days=float(duration_days),
        summary=f"If {sme_name} is unavailable for {duration_days}d: {affected} proposal(s) impacted, {revenue_at_risk:.2f} Cr at risk.",
        factors=factors,
        confidence=0.75 if sme_id else 0.40,
    )


def _simulate_approval_delayed(db: "Session", params: dict, snapshot: dict) -> SimulationImpact:
    from sqlalchemy import select
    from models import Approval, Proposal
    from models.opportunity import Opportunity

    delay_hours = float(params.get("delay_hours", 48))
    stage = params.get("stage")  # optional — filter to specific stage

    query = select(Approval).where(Approval.status == "pending")
    if stage:
        query = query.where(Approval.stage == stage)
    pending = db.scalars(query).all()

    affected_proposal_ids = list({a.proposal_id for a in pending})
    opp_ids = []
    for pid in affected_proposal_ids:
        p = db.get(Proposal, pid)
        if p and p.opportunity_id:
            opp_ids.append(p.opportunity_id)

    revenue_at_risk = 0.0
    if opp_ids:
        opps = db.scalars(select(Opportunity).where(Opportunity.id.in_(opp_ids))).all()
        revenue_at_risk = sum(float(o.deal_value_cr or 0) for o in opps)

    delay_days = delay_hours / 24
    sla_increase = min(0.50, len(pending) * 0.03 + delay_days * 0.04)

    factors = [
        f"{len(pending)} pending approval(s) affected",
        f"Additional delay: {delay_hours:.0f}h ({delay_days:.1f}d)",
        f"SLA breach probability increases by ~{sla_increase:.0%}",
    ]
    if stage:
        factors.append(f"Bottleneck concentrated in '{stage}' stage")

    stage_label = f"'{stage}' stage" if stage else "all stages"
    return SimulationImpact(
        affected_proposals=len(affected_proposal_ids),
        revenue_at_risk_cr=round(revenue_at_risk, 3),
        sla_risk_increase=round(sla_increase, 3),
        capacity_impact="mild" if delay_hours <= 24 else "moderate" if delay_hours <= 72 else "severe",
        escalation_risk_increase=min(0.30, delay_days * 0.05),
        timeline_delay_days=round(delay_days, 1),
        summary=f"If approvals in {stage_label} delay {delay_hours:.0f}h: {len(affected_proposal_ids)} proposals impacted.",
        factors=factors,
        confidence=0.70,
    )


def _simulate_rfp_surge(db: "Session", params: dict, snapshot: dict) -> SimulationImpact:
    from sqlalchemy import select
    from models.stakeholder import Stakeholder

    new_rfps = int(params.get("new_rfp_count", 10))
    stakeholders = db.scalars(select(Stakeholder)).all()
    total_smes = len(stakeholders)
    avg_workload = snapshot.get("avg_workload", 0)
    current_active = snapshot.get("active_proposals", 0)

    # Estimate capacity headroom
    headroom_per_sme = max(0, SME_SATURATION_WORKLOAD - avg_workload)
    total_headroom = headroom_per_sme * total_smes
    overflow = max(0, new_rfps - total_headroom)

    capacity_impact = "none"
    if overflow > 0:
        capacity_impact = "severe" if overflow >= total_smes else "moderate"
    elif new_rfps > total_headroom * 0.5:
        capacity_impact = "mild"

    sla_risk_increase = min(0.45, new_rfps / max(total_smes * headroom_per_sme, 1) * 0.3)

    factors = [
        f"{new_rfps} new RFPs arriving simultaneously",
        f"Current SME headroom: {total_headroom:.0f} units across {total_smes} SMEs",
        f"Overflow (unabsorbable): {overflow:.0f} units",
    ]
    if overflow > 0:
        factors.append(f"Requires {overflow} additional SME-workload-units — hiring or redistribution needed")

    return SimulationImpact(
        affected_proposals=new_rfps,
        revenue_at_risk_cr=0.0,  # revenue not known for hypothetical RFPs
        sla_risk_increase=round(sla_risk_increase, 3),
        capacity_impact=capacity_impact,
        escalation_risk_increase=min(0.20, overflow / max(total_smes, 1) * 0.10),
        timeline_delay_days=round(overflow / max(total_smes, 1) * 2, 1),
        summary=f"If {new_rfps} RFPs arrive: {overflow:.0f} unit overflow beyond current capacity.",
        factors=factors,
        confidence=0.65,
    )


def _simulate_bu_overloaded(db: "Session", params: dict, snapshot: dict) -> SimulationImpact:
    from sqlalchemy import select
    from models.proposal import Assignment
    from models.stakeholder import Stakeholder
    from models.opportunity import Opportunity
    from models import Proposal

    bu_name = params.get("bu", "")
    smes_in_bu = db.scalars(
        select(Stakeholder).where(Stakeholder.bu == bu_name)
    ).all() if bu_name else []

    sme_ids = {s.id for s in smes_in_bu}
    assignments = [
        a for a in db.scalars(select(Assignment)).all()
        if a.stakeholder_id in sme_ids
    ]
    affected_pids = list({a.proposal_id for a in assignments})

    opp_ids = []
    for pid in affected_pids:
        p = db.get(Proposal, pid)
        if p and p.opportunity_id:
            opp_ids.append(p.opportunity_id)

    revenue_at_risk = 0.0
    if opp_ids:
        opps = db.scalars(select(Opportunity).where(Opportunity.id.in_(opp_ids))).all()
        revenue_at_risk = sum(float(o.deal_value_cr or 0) for o in opps)

    capacity_impact = "severe" if len(smes_in_bu) > 0 else "none"
    factors = [
        f"BU '{bu_name}' has {len(smes_in_bu)} SME(s) at saturation",
        f"{len(affected_pids)} proposal(s) assigned to this BU",
        f"{revenue_at_risk:.2f} Cr in pipeline depends on this BU",
    ]

    return SimulationImpact(
        affected_proposals=len(affected_pids),
        revenue_at_risk_cr=round(revenue_at_risk, 3),
        sla_risk_increase=min(0.45, len(smes_in_bu) * 0.08),
        capacity_impact=capacity_impact,
        escalation_risk_increase=min(0.35, len(affected_pids) * 0.04),
        timeline_delay_days=float(len(smes_in_bu) * 3),
        summary=f"If BU '{bu_name}' reaches capacity: {len(affected_pids)} proposals at risk, {revenue_at_risk:.2f} Cr exposed.",
        factors=factors,
        confidence=0.68,
    )


def _simulate_proposal_rejected(db: "Session", params: dict, snapshot: dict) -> SimulationImpact:
    from sqlalchemy import select
    from models import Proposal, Approval
    from models.opportunity import Opportunity

    proposal_id = params.get("proposal_id", "")
    p = db.get(Proposal, proposal_id) if proposal_id else None

    if not p:
        return SimulationImpact(
            affected_proposals=0,
            revenue_at_risk_cr=0.0,
            sla_risk_increase=0.0,
            capacity_impact="none",
            escalation_risk_increase=0.0,
            timeline_delay_days=0.0,
            summary="Proposal not found — cannot simulate rejection impact.",
            factors=["Proposal ID not found"],
            confidence=0.10,
        )

    opp = db.get(Opportunity, p.opportunity_id) if p.opportunity_id else None
    val = float(opp.deal_value_cr or 0) if opp else 0.0
    stage_weight = STAGE_CLOSE_WEIGHTS.get(p.stage, 0.10)
    value_foregone = val * stage_weight

    approvals = db.scalars(
        select(Approval).where(Approval.proposal_id == proposal_id)
    ).all()
    approval_effort = len(approvals) * 0.5  # days of review effort lost

    factors = [
        f"Proposal in '{p.stage}' stage (close weight {stage_weight:.0%})",
        f"Deal value {val:.2f} Cr — weighted value foregone: {value_foregone:.2f} Cr",
        f"{len(approvals)} approval(s) completed — effort lost",
    ]
    if val >= 5:
        factors.append("High-value deal rejection — significant revenue impact")

    return SimulationImpact(
        affected_proposals=1,
        revenue_at_risk_cr=round(value_foregone, 3),
        sla_risk_increase=0.0,
        capacity_impact="mild",
        escalation_risk_increase=0.0,
        timeline_delay_days=0.0,
        summary=f"If proposal rejected: {value_foregone:.2f} Cr weighted revenue foregone, {approval_effort:.1f} days review effort lost.",
        factors=factors,
        confidence=0.85,
    )


_SIMULATORS = {
    "sme_unavailable": _simulate_sme_unavailable,
    "approval_delayed": _simulate_approval_delayed,
    "rfp_surge": _simulate_rfp_surge,
    "bu_overloaded": _simulate_bu_overloaded,
    "proposal_rejected": _simulate_proposal_rejected,
}


def run_what_if(db: "Session", scenario: SimulationScenario) -> SimulationResult:
    snapshot = _snapshot_current_state(db)
    simulator = _SIMULATORS[scenario.scenario_type]
    impact = simulator(db, scenario.parameters, snapshot)

    projected = dict(snapshot)
    projected["active_proposals"] = snapshot["active_proposals"] + impact.affected_proposals
    projected["total_pipeline_cr"] = max(0, snapshot["total_pipeline_cr"] - impact.revenue_at_risk_cr)

    recs: list[str] = []
    if impact.capacity_impact in ("moderate", "severe"):
        recs.append("Review SME capacity — redistribute workload before scenario materializes")
    if impact.sla_risk_increase > 0.20:
        recs.append("Increase approval monitoring frequency to mitigate SLA breach risk")
    if impact.revenue_at_risk_cr > 2:
        recs.append(f"Escalate to leadership — {impact.revenue_at_risk_cr:.2f} Cr at risk")
    if not recs:
        recs.append("No immediate action required — monitor standard KPIs")

    return SimulationResult(
        scenario_type=scenario.scenario_type,
        scenario_label=scenario.label,
        parameters=scenario.parameters,
        impact=impact,
        current_state_snapshot=snapshot,
        projected_state=projected,
        recommendations=recs,
        simulated_at=datetime.now(timezone.utc).isoformat(),
    )
