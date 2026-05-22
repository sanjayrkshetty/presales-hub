"""
Decision Intelligence API.

All endpoints are read-only GET (compute + return) except /health/recompute.
Scores are persisted to the intelligence tables for auditability.

Endpoints:
  GET  /api/intelligence/proposals/{id}/health
  POST /api/intelligence/proposals/{id}/health/recompute
  GET  /api/intelligence/proposals/{id}/sla-risk
  GET  /api/intelligence/proposals/{id}/sme-candidates
  GET  /api/intelligence/bottlenecks
  GET  /api/intelligence/anomalies
  GET  /api/intelligence/throughput
  GET  /api/intelligence/opportunities/{id}/risk
  GET  /api/intelligence/dashboard
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from db.database import get_db
from models import (
    Proposal, Opportunity, Stakeholder, Assignment, Approval,
    SlaConfig, AuditLog, SmeRoutingRule,
)
from models.intelligence import (
    ProposalScore, SlaPrediction, BottleneckSnapshot,
    SmeRecommendationAudit, ApprovalAnomaly,
)
from decision_engine.scoring.health import compute_health_score, enrich_with_llm
from decision_engine.scoring.deal_risk import compute_deal_risk
from decision_engine.predictors.sla_breach import predict_breach
from decision_engine.predictors.bottleneck import detect_bottlenecks, ProposalStageSnapshot
from decision_engine.recommendations.sme_ranker import rank_sme_candidates
from decision_engine.anomaly_detection.approval_anomaly import scan_approval, detect_sequential_self_approval
from decision_engine.analytics.throughput import compute_throughput
from decision_engine.analytics.opportunity_intel import build_opportunity_intelligence
from telemetry.context import set_proposal_id

logger = logging.getLogger("routers.decision_intelligence")

router = APIRouter(prefix="/api/intelligence", tags=["decision-intelligence"])


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_proposal_or_404(proposal_id: str, db: Session) -> Proposal:
    p = db.scalar(select(Proposal).where(Proposal.id == proposal_id))
    if not p:
        raise HTTPException(404, f"Proposal {proposal_id} not found")
    return p


def _get_opportunity_or_404(opportunity_id: str, db: Session) -> Opportunity:
    o = db.scalar(select(Opportunity).where(Opportunity.id == opportunity_id))
    if not o:
        raise HTTPException(404, f"Opportunity {opportunity_id} not found")
    return o


def _load_proposal_context(proposal: Proposal, db: Session):
    assignments = db.scalars(
        select(Assignment).where(Assignment.proposal_id == proposal.id)
    ).all()
    approvals = db.scalars(
        select(Approval).where(Approval.proposal_id == proposal.id)
    ).all()
    return assignments, approvals


def _persist_score(proposal_id: str, health, triggered_by: str, db: Session) -> ProposalScore:
    record = ProposalScore(
        proposal_id=proposal_id,
        overall_score=health.overall_score,
        breakdown=health.breakdown.__dict__ if hasattr(health.breakdown, "__dict__") else health.breakdown,
        risk_factors=health.risk_factors,
        missing_requirements=health.missing_requirements,
        readiness_classification=health.readiness_classification,
        explanation=health.explanation,
        model_version=health.model_version,
        triggered_by=triggered_by,
    )
    db.add(record)
    # Update proposal.health_score field
    proposal = db.scalar(select(Proposal).where(Proposal.id == proposal_id))
    if proposal:
        proposal.health_score = health.overall_score
    db.commit()
    return record


def _stage_entered_at(proposal_id: str, stage: str, db: Session) -> datetime:
    """
    Approximate when proposal entered current stage from AuditLog.
    Falls back to utcnow() - 1h if no record found.
    """
    row = db.scalar(
        select(AuditLog)
        .where(
            and_(
                AuditLog.entity_id == proposal_id,
                AuditLog.entity_type == "proposal",
                AuditLog.action == "stage_transition",
                AuditLog.to_state == stage,
            )
        )
        .order_by(AuditLog.occurred_at.desc())
    )
    if row:
        return row.occurred_at
    return datetime.utcnow()


def _historical_success_rates(candidate_ids: list[str], db: Session) -> dict[str, float]:
    """
    Compute per-SME approval success rate from AuditLog.
    success = approved decisions / (approved + rejected) decisions.
    """
    rates = {}
    for sid in candidate_ids:
        total = db.scalar(
            select(func.count(AuditLog.id))
            .where(
                and_(
                    AuditLog.actor_id == sid,
                    AuditLog.action.in_(["approval_approved", "approval_rejected"]),
                )
            )
        ) or 0
        approved = db.scalar(
            select(func.count(AuditLog.id))
            .where(
                and_(
                    AuditLog.actor_id == sid,
                    AuditLog.action == "approval_approved",
                )
            )
        ) or 0
        rates[sid] = (approved / total) if total > 0 else 0.5
    return rates


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/proposals/{proposal_id}/health")
def get_proposal_health(proposal_id: str, db: Session = Depends(get_db)):
    """Return the most recent persisted health score, or compute one if none exists."""
    set_proposal_id(proposal_id)
    latest = db.scalar(
        select(ProposalScore)
        .where(ProposalScore.proposal_id == proposal_id)
        .order_by(ProposalScore.scored_at.desc())
    )
    if latest:
        return {
            "proposal_id": proposal_id,
            "overall_score": latest.overall_score,
            "readiness_classification": latest.readiness_classification,
            "breakdown": latest.breakdown,
            "risk_factors": latest.risk_factors,
            "missing_requirements": latest.missing_requirements,
            "explanation": latest.explanation,
            "model_version": latest.model_version,
            "scored_at": latest.scored_at.isoformat(),
            "cached": True,
        }

    # Nothing stored yet — compute on the fly
    proposal = _get_proposal_or_404(proposal_id, db)
    assignments, approvals = _load_proposal_context(proposal, db)
    opp = db.scalar(select(Opportunity).where(Opportunity.id == proposal.opportunity_id))
    deadline = opp.deadline if opp else None

    health = compute_health_score(
        proposal_id=proposal_id,
        stage=proposal.stage,
        content=proposal.content or {},
        assignments=list(assignments),
        approvals=list(approvals),
        deadline=deadline,
    )
    _persist_score(proposal_id, health, "api", db)
    result = health.to_dict()
    result["cached"] = False
    return result


@router.post("/proposals/{proposal_id}/health/recompute")
async def recompute_proposal_health(
    proposal_id: str,
    enrich: bool = Query(False, description="Call LLM for narrative explanation"),
    db: Session = Depends(get_db),
):
    """Force a fresh health score computation and persist it."""
    set_proposal_id(proposal_id)
    proposal = _get_proposal_or_404(proposal_id, db)
    assignments, approvals = _load_proposal_context(proposal, db)
    opp = db.scalar(select(Opportunity).where(Opportunity.id == proposal.opportunity_id))
    deadline = opp.deadline if opp else None

    health = compute_health_score(
        proposal_id=proposal_id,
        stage=proposal.stage,
        content=proposal.content or {},
        assignments=list(assignments),
        approvals=list(approvals),
        deadline=deadline,
    )
    if enrich:
        health = await enrich_with_llm(health, proposal.content or {})

    _persist_score(proposal_id, health, "api_recompute", db)
    result = health.to_dict()
    result["cached"] = False
    return result


@router.get("/proposals/{proposal_id}/sla-risk")
def get_sla_risk(proposal_id: str, db: Session = Depends(get_db)):
    """Predict SLA breach probability for the proposal's current stage."""
    set_proposal_id(proposal_id)
    proposal = _get_proposal_or_404(proposal_id, db)
    opp = db.scalar(select(Opportunity).where(Opportunity.id == proposal.opportunity_id))
    if not opp:
        raise HTTPException(404, "Linked opportunity not found")

    sla_cfg = db.scalar(select(SlaConfig).where(SlaConfig.stage == proposal.stage))
    sla_hours = sla_cfg.hours_allowed if sla_cfg else 24

    stage_entered = _stage_entered_at(proposal_id, proposal.stage, db)

    pending_approvals = db.scalar(
        select(func.count(Approval.id))
        .where(
            and_(
                Approval.proposal_id == proposal_id,
                Approval.status == "pending",
            )
        )
    ) or 0

    assignments = db.scalars(
        select(Assignment).where(
            and_(Assignment.proposal_id == proposal_id, Assignment.status != "completed")
        )
    ).all()
    sme_workload = 0
    if assignments:
        sme = db.scalar(
            select(Stakeholder).where(Stakeholder.id == assignments[0].stakeholder_id)
        )
        sme_workload = sme.current_workload if sme else 0

    risk = predict_breach(
        proposal_id=proposal_id,
        stage=proposal.stage,
        stage_entered_at=stage_entered,
        sla_hours=sla_hours,
        pending_approvals=pending_approvals,
        sme_workload=sme_workload,
    )

    # Persist prediction
    db.add(SlaPrediction(
        proposal_id=proposal_id,
        opportunity_id=opp.id,
        stage=proposal.stage,
        breach_probability=risk.breach_probability,
        predicted_hours_to_breach=risk.predicted_hours_to_breach,
        risk_level=risk.risk_level,
        factors=risk.factors,
    ))
    db.commit()

    return risk.to_dict()


@router.get("/proposals/{proposal_id}/sme-candidates")
def get_sme_candidates(proposal_id: str, db: Session = Depends(get_db)):
    """Rank all eligible SMEs for this proposal using composite scoring."""
    set_proposal_id(proposal_id)
    proposal = _get_proposal_or_404(proposal_id, db)
    opp = db.scalar(select(Opportunity).where(Opportunity.id == proposal.opportunity_id))
    rfp_type = opp.rfp_type if opp else None

    # Load required expertise from routing rules
    required_expertise: list[str] = []
    if rfp_type:
        rules = db.scalars(
            select(SmeRoutingRule)
            .where(SmeRoutingRule.rfp_type == rfp_type)
            .order_by(SmeRoutingRule.priority)
        ).all()
        required_expertise = [r.required_expertise for r in rules]

    # All SMEs (role == "sme") with workload < 4
    candidates = db.scalars(
        select(Stakeholder)
        .where(
            and_(
                Stakeholder.role == "sme",
                Stakeholder.current_workload < 4,
            )
        )
    ).all()

    candidate_ids = [c.id for c in candidates]
    hist = _historical_success_rates(candidate_ids, db)

    result = rank_sme_candidates(
        proposal_id=proposal_id,
        rfp_type=rfp_type,
        required_expertise=required_expertise,
        candidates=list(candidates),
        historical_success=hist,
    )

    # Persist recommendation audit
    db.add(SmeRecommendationAudit(
        proposal_id=proposal_id,
        rfp_type=rfp_type,
        ranked_candidates=[c.to_dict() for c in result.ranked],
        outcome="pending",
    ))
    db.commit()

    return result.to_dict()


@router.get("/bottlenecks")
def get_bottlenecks(db: Session = Depends(get_db)):
    """Identify stages where multiple proposals are simultaneously stalled."""
    proposals = db.scalars(
        select(Proposal).where(
            Proposal.stage.not_in(["closed_won", "closed_lost"])
        )
    ).all()

    sla_map = {r.stage: r.hours_allowed for r in db.scalars(select(SlaConfig)).all()}

    snapshots: list[ProposalStageSnapshot] = []
    for p in proposals:
        sla_hours = sla_map.get(p.stage, 24)
        stage_entered = _stage_entered_at(p.id, p.stage, db)
        elapsed = (datetime.utcnow() - stage_entered).total_seconds() / 3600
        pending = db.scalar(
            select(func.count(Approval.id))
            .where(and_(Approval.proposal_id == p.id, Approval.status == "pending"))
        ) or 0
        snapshots.append(ProposalStageSnapshot(
            proposal_id=p.id,
            stage=p.stage,
            elapsed_hours=elapsed,
            sla_hours=sla_hours,
            pending_approvals=pending,
        ))

    predictions = detect_bottlenecks(snapshots)

    # Persist high/medium bottlenecks
    for pred in predictions:
        if pred.severity in {"high", "medium"}:
            db.add(BottleneckSnapshot(
                stage=pred.stage,
                severity=pred.severity,
                affected_count=pred.affected_count,
                estimated_delay_hours=pred.estimated_delay_hours,
                factors=pred.factors,
            ))
    if predictions:
        db.commit()

    return {
        "bottlenecks": [p.to_dict() for p in predictions],
        "total": len(predictions),
        "has_high_severity": any(p.severity == "high" for p in predictions),
    }


@router.get("/anomalies")
def get_anomalies(
    acknowledged: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """Return recent approval anomalies, optionally filtered by acknowledged state."""
    q = select(ApprovalAnomaly).order_by(ApprovalAnomaly.detected_at.desc()).limit(limit)
    if acknowledged is not None:
        q = q.where(ApprovalAnomaly.acknowledged == acknowledged)
    rows = db.scalars(q).all()

    return {
        "anomalies": [
            {
                "id": r.id,
                "proposal_id": r.proposal_id,
                "approval_id": r.approval_id,
                "anomaly_type": r.anomaly_type,
                "severity": r.severity,
                "details": r.details,
                "acknowledged": r.acknowledged,
                "detected_at": r.detected_at.isoformat(),
            }
            for r in rows
        ],
        "total": len(rows),
        "unacknowledged": sum(1 for r in rows if not r.acknowledged),
    }


@router.post("/anomalies/{anomaly_id}/acknowledge")
def acknowledge_anomaly(anomaly_id: str, db: Session = Depends(get_db)):
    row = db.scalar(select(ApprovalAnomaly).where(ApprovalAnomaly.id == anomaly_id))
    if not row:
        raise HTTPException(404, "Anomaly not found")
    row.acknowledged = True
    db.commit()
    return {"acknowledged": True, "anomaly_id": anomaly_id}


@router.get("/throughput")
def get_throughput(db: Session = Depends(get_db)):
    """Compute workflow throughput metrics from AuditLog stage transitions."""
    audit_rows = db.scalars(
        select(AuditLog)
        .where(
            and_(
                AuditLog.action == "stage_transition",
                AuditLog.entity_type == "proposal",
            )
        )
        .order_by(AuditLog.occurred_at.asc())
    ).all()

    sla_config = {r.stage: r.hours_allowed for r in db.scalars(select(SlaConfig)).all()}
    report = compute_throughput(list(audit_rows), sla_config)
    return report.to_dict()


@router.get("/opportunities/{opportunity_id}/risk")
async def get_opportunity_risk(
    opportunity_id: str,
    enrich: bool = Query(False, description="Call LLM for risk narrative"),
    db: Session = Depends(get_db),
):
    """Compute a deal risk score for the opportunity."""
    opp = _get_opportunity_or_404(opportunity_id, db)
    proposal = db.scalar(select(Proposal).where(Proposal.opportunity_id == opportunity_id))

    total_approvals = pending_approvals = 0
    if proposal:
        total_approvals = db.scalar(
            select(func.count(Approval.id)).where(Approval.proposal_id == proposal.id)
        ) or 0
        pending_approvals = db.scalar(
            select(func.count(Approval.id)).where(
                and_(Approval.proposal_id == proposal.id, Approval.status == "pending")
            )
        ) or 0

    intel = build_opportunity_intelligence(
        opportunity=opp,
        proposal=proposal,
        pending_approvals=pending_approvals,
        total_approvals=total_approvals,
    )

    result = intel.to_dict()

    if enrich:
        try:
            from decision_engine.prompts.risk_assessment import build_risk_narrative
            narrative = await build_risk_narrative(intel.deal_risk)
            result["risk_narrative"] = narrative
        except Exception:
            result["risk_narrative"] = None

    return result


@router.get("/dashboard")
def get_intelligence_dashboard(db: Session = Depends(get_db)):
    """
    Unified intelligence dashboard.
    Aggregates: active anomalies, active bottlenecks, high-risk proposals,
    throughput summary, and latest score distribution.
    """
    # Unacknowledged anomalies
    anomaly_count = db.scalar(
        select(func.count(ApprovalAnomaly.id))
        .where(ApprovalAnomaly.acknowledged == False)  # noqa: E712
    ) or 0
    high_anomalies = db.scalar(
        select(func.count(ApprovalAnomaly.id))
        .where(
            and_(
                ApprovalAnomaly.acknowledged == False,  # noqa: E712
                ApprovalAnomaly.severity == "high",
            )
        )
    ) or 0

    # Latest bottleneck snapshots (last hour)
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(hours=1)
    recent_bottlenecks = db.scalars(
        select(BottleneckSnapshot)
        .where(BottleneckSnapshot.captured_at >= cutoff)
        .order_by(BottleneckSnapshot.captured_at.desc())
        .limit(10)
    ).all()

    # Score distribution from proposal_scores (latest per proposal via subquery)
    from sqlalchemy import alias
    latest_subq = (
        select(
            ProposalScore.proposal_id,
            func.max(ProposalScore.scored_at).label("max_scored_at"),
        )
        .group_by(ProposalScore.proposal_id)
        .subquery()
    )
    all_scores = db.scalars(
        select(ProposalScore.overall_score)
        .join(
            latest_subq,
            (ProposalScore.proposal_id == latest_subq.c.proposal_id)
            & (ProposalScore.scored_at == latest_subq.c.max_scored_at),
        )
    ).all()
    distribution = {"green": 0, "yellow": 0, "orange": 0, "red": 0}
    for s in all_scores:
        if s >= 80:
            distribution["green"] += 1
        elif s >= 60:
            distribution["yellow"] += 1
        elif s >= 40:
            distribution["orange"] += 1
        else:
            distribution["red"] += 1

    # Critical SLA predictions
    critical_sla = db.scalars(
        select(SlaPrediction)
        .where(SlaPrediction.risk_level.in_(["critical", "high"]))
        .order_by(SlaPrediction.predicted_at.desc())
        .limit(5)
    ).all()

    return {
        "anomalies": {
            "total_unacknowledged": anomaly_count,
            "high_severity": high_anomalies,
        },
        "bottlenecks": [
            {
                "stage": b.stage,
                "severity": b.severity,
                "affected_count": b.affected_count,
                "estimated_delay_hours": b.estimated_delay_hours,
            }
            for b in recent_bottlenecks
        ],
        "score_distribution": distribution,
        "total_proposals_scored": sum(distribution.values()),
        "critical_sla_risks": [
            {
                "proposal_id": r.proposal_id,
                "stage": r.stage,
                "risk_level": r.risk_level,
                "breach_probability": round(r.breach_probability, 3),
            }
            for r in critical_sla
        ],
    }
