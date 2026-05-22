"""
Team capacity forecasting: SME overload, approval bottlenecks, saturation,
burnout indicators, proposal throughput degradation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from strategic_intelligence.config import (
    APPROVAL_BOTTLENECK_THRESHOLD,
    BURNOUT_WORKLOAD_RATIO,
    SME_SATURATION_WORKLOAD,
    SME_WARNING_WORKLOAD,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class SMECapacityProfile:
    stakeholder_id: str
    name: str
    role: str
    bu: str
    current_workload: int
    saturation_pct: float          # 0.0–1.0
    risk_level: str                # ok | warning | overloaded | burnout_risk
    active_proposals: int
    pending_approvals: int
    burnout_risk: bool
    rationale: str


@dataclass
class ApprovalBottleneck:
    stage: str
    pending_count: int
    overdue_count: int
    avg_age_days: float
    severity: str                  # low | medium | high | critical
    blocking_stakeholder_ids: list[str]
    rationale: str


@dataclass
class CapacityReport:
    snapshot_time: str
    total_smes: int
    overloaded_smes: int
    at_risk_smes: int
    burnout_risk_count: int
    saturation_pct: float
    pending_approvals: int
    bottleneck_stages: list[ApprovalBottleneck]
    sme_profiles: list[SMECapacityProfile]
    throughput_risk: str           # low | medium | high
    throughput_rationale: str
    overall_capacity_label: str    # healthy | strained | critical
    recommendations: list[str]


def _sme_risk_level(workload: int) -> tuple[str, bool]:
    """Returns (risk_level, burnout_risk)."""
    ratio = workload / SME_SATURATION_WORKLOAD
    burnout = ratio >= BURNOUT_WORKLOAD_RATIO
    if workload >= SME_SATURATION_WORKLOAD:
        return "overloaded", burnout
    if workload >= SME_WARNING_WORKLOAD:
        return "warning", burnout
    return "ok", False


def _approval_severity(count: int, overdue: int) -> str:
    if overdue >= 3 or count >= APPROVAL_BOTTLENECK_THRESHOLD * 2:
        return "critical"
    if overdue >= 1 or count >= APPROVAL_BOTTLENECK_THRESHOLD:
        return "high"
    if count >= APPROVAL_BOTTLENECK_THRESHOLD - 1:
        return "medium"
    return "low"


def compute_capacity_report(db: "Session") -> CapacityReport:
    from sqlalchemy import select
    from models.stakeholder import Stakeholder
    from models import Proposal, Approval

    now = datetime.now(timezone.utc)

    stakeholders = db.scalars(
        select(Stakeholder).where(Stakeholder.role.in_(["sme", "approver", "reviewer"]))
    ).all()
    all_stakeholders = db.scalars(select(Stakeholder)).all()

    # Map stakeholder → active proposals (via Assignment or Approval)
    from models.proposal import Assignment
    assignments = db.scalars(select(Assignment)).all()
    sme_proposal_count: dict[str, int] = {}
    for a in assignments:
        sme_proposal_count[a.stakeholder_id] = sme_proposal_count.get(a.stakeholder_id, 0) + 1

    all_approvals = db.scalars(select(Approval)).all()
    pending_by_stage: dict[str, list[Approval]] = {}
    sme_pending_count: dict[str, int] = {}
    for appr in all_approvals:
        if appr.status == "pending":
            pending_by_stage.setdefault(appr.stage or "unknown", []).append(appr)
            if appr.approver_id:
                sme_pending_count[appr.approver_id] = sme_pending_count.get(appr.approver_id, 0) + 1

    # Build SME profiles
    sme_profiles: list[SMECapacityProfile] = []
    overloaded = 0
    at_risk = 0
    burnout_count = 0
    saturation_sum = 0.0

    for s in all_stakeholders:
        workload = s.current_workload or 0
        active_proposals = sme_proposal_count.get(s.id, 0)
        pending_approvals = sme_pending_count.get(s.id, 0)
        effective_workload = max(workload, active_proposals + pending_approvals)
        risk_level, burnout = _sme_risk_level(effective_workload)
        sat_pct = min(1.0, effective_workload / SME_SATURATION_WORKLOAD)
        saturation_sum += sat_pct

        if risk_level == "overloaded":
            overloaded += 1
        elif risk_level == "warning":
            at_risk += 1
        if burnout:
            burnout_count += 1

        rationale = (
            f"Workload {effective_workload}/{SME_SATURATION_WORKLOAD} "
            f"({sat_pct:.0%} saturation). "
            f"{active_proposals} active proposal(s), {pending_approvals} pending approval(s)."
        )

        sme_profiles.append(SMECapacityProfile(
            stakeholder_id=s.id,
            name=s.name,
            role=s.role or "unknown",
            bu=s.bu or "unassigned",
            current_workload=effective_workload,
            saturation_pct=round(sat_pct, 3),
            risk_level=risk_level,
            active_proposals=active_proposals,
            pending_approvals=pending_approvals,
            burnout_risk=burnout,
            rationale=rationale,
        ))

    total_smes = len(all_stakeholders)
    avg_saturation = saturation_sum / total_smes if total_smes else 0.0

    # Approval bottlenecks
    bottlenecks: list[ApprovalBottleneck] = []
    total_pending = sum(len(v) for v in pending_by_stage.values())

    for stage, approvals in pending_by_stage.items():
        overdue_approvals = [
            a for a in approvals
            if a.due_at and a.due_at.replace(tzinfo=timezone.utc) < now
        ]
        ages = []
        for a in approvals:
            if a.created_at:
                created = a.created_at.replace(tzinfo=timezone.utc) if a.created_at.tzinfo is None else a.created_at
                ages.append((now - created).days)
        avg_age = sum(ages) / len(ages) if ages else 0.0
        severity = _approval_severity(len(approvals), len(overdue_approvals))
        blocking_ids = list({a.approver_id for a in approvals if a.approver_id})

        if severity in ("high", "critical") or len(approvals) >= APPROVAL_BOTTLENECK_THRESHOLD:
            rationale = (
                f"{len(approvals)} pending approval(s) in '{stage}'. "
                f"{len(overdue_approvals)} overdue. Avg age: {avg_age:.1f} days."
            )
            bottlenecks.append(ApprovalBottleneck(
                stage=stage,
                pending_count=len(approvals),
                overdue_count=len(overdue_approvals),
                avg_age_days=round(avg_age, 1),
                severity=severity,
                blocking_stakeholder_ids=blocking_ids,
                rationale=rationale,
            ))

    bottlenecks.sort(key=lambda b: ["low", "medium", "high", "critical"].index(b.severity), reverse=True)

    # Throughput risk
    if overloaded > total_smes * 0.4 or len([b for b in bottlenecks if b.severity == "critical"]) >= 2:
        throughput_risk = "high"
        throughput_rationale = f"{overloaded} overloaded SMEs + {len(bottlenecks)} bottleneck stages will degrade throughput."
    elif at_risk > total_smes * 0.3 or any(b.severity in ("high", "critical") for b in bottlenecks):
        throughput_risk = "medium"
        throughput_rationale = "Warning-level SME load and approval delays may slow proposal advancement."
    else:
        throughput_risk = "low"
        throughput_rationale = "Capacity appears sufficient for current pipeline volume."

    # Overall label
    if overloaded > 0 or any(b.severity == "critical" for b in bottlenecks):
        overall_label = "critical"
    elif at_risk > 0 or any(b.severity == "high" for b in bottlenecks):
        overall_label = "strained"
    else:
        overall_label = "healthy"

    # Recommendations
    recs: list[str] = []
    for p in sme_profiles:
        if p.risk_level == "overloaded":
            recs.append(f"Redistribute workload from {p.name} (overloaded at {p.saturation_pct:.0%})")
    for b in bottlenecks:
        if b.severity in ("high", "critical"):
            recs.append(f"Escalate '{b.stage}' bottleneck — {b.pending_count} approvals pending")
    if burnout_count > 0:
        recs.append(f"{burnout_count} SME(s) at burnout risk — schedule workload review")

    sme_profiles.sort(key=lambda p: p.saturation_pct, reverse=True)

    return CapacityReport(
        snapshot_time=now.isoformat(),
        total_smes=total_smes,
        overloaded_smes=overloaded,
        at_risk_smes=at_risk,
        burnout_risk_count=burnout_count,
        saturation_pct=round(avg_saturation, 3),
        pending_approvals=total_pending,
        bottleneck_stages=bottlenecks,
        sme_profiles=sme_profiles,
        throughput_risk=throughput_risk,
        throughput_rationale=throughput_rationale,
        overall_capacity_label=overall_label,
        recommendations=recs,
    )
