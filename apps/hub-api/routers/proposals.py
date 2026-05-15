from datetime import datetime, timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from db.database import get_db
from models import Proposal, Stakeholder, Assignment, ActivityFeed, AuditLog, SlaConfig, SmeRoutingRule
from models.proposal import TRANSITIONS, PARALLEL_REVIEW_GROUP

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


class TransitionRequest(BaseModel):
    to_stage: str
    actor_id: str | None = None
    note: str | None = None


class AssignSmeRequest(BaseModel):
    rfp_type: str
    required_skills: list[str] | None = None


def _add_activity(db: Session, proposal_id: str, actor_name: str, action_type: str, description: str, is_alert: bool = False):
    db.add(ActivityFeed(
        proposal_id=proposal_id,
        actor_name=actor_name,
        action_type=action_type,
        description=description,
        is_alert=is_alert,
    ))


@router.post("/{proposal_id}/transition")
def transition_proposal(proposal_id: str, req: TransitionRequest, db: Session = Depends(get_db)):
    proposal = db.scalar(select(Proposal).where(Proposal.id == proposal_id))
    if not proposal:
        raise HTTPException(404, "Proposal not found")

    allowed = TRANSITIONS.get(proposal.stage, [])
    if req.to_stage not in allowed:
        raise HTTPException(422, f"Invalid transition: {proposal.stage} → {req.to_stage}. Allowed: {allowed}")

    # For parallel review stages, entering any one of them starts that stage
    # Exiting to finance_review requires all three completed (handled via approvals, simplified here)
    if req.to_stage in PARALLEL_REVIEW_GROUP and proposal.stage == "drafting":
        # Create parallel approvals for all 3 review stages if not already present
        existing_stages = {a.stage for a in proposal.approvals}
        for review_stage in sorted(PARALLEL_REVIEW_GROUP):
            if review_stage not in existing_stages:
                sla = db.get(SlaConfig, review_stage)
                due = datetime.utcnow() + timedelta(hours=sla.hours_allowed) if sla else None
                db.add(Assignment(
                    proposal_id=proposal.id,
                    stakeholder_id=None,
                    role="reviewer",
                    bu=None,
                    status="pending",
                    due_at=due,
                ))

    from_stage = proposal.stage
    proposal.stage = req.to_stage
    proposal.updated_at = datetime.utcnow()

    if req.to_stage == "submission":
        proposal.submitted_at = datetime.utcnow()

    # Sync opportunity stage
    if proposal.opportunity:
        proposal.opportunity.stage = req.to_stage
        proposal.opportunity.updated_at = datetime.utcnow()

    actor_name = "System"
    if req.actor_id:
        actor = db.get(Stakeholder, req.actor_id)
        if actor:
            actor_name = actor.name

    db.add(AuditLog(
        entity_type="proposal",
        entity_id=proposal.id,
        actor_id=req.actor_id,
        action="stage_transition",
        from_state=from_stage,
        to_state=req.to_stage,
        meta={"note": req.note or ""},
    ))

    _add_activity(
        db, proposal.id, actor_name, "stage_transition",
        f"Moved to {req.to_stage.replace('_', ' ').title()}",
    )

    db.commit()
    return {"proposal_id": proposal_id, "from_stage": from_stage, "to_stage": req.to_stage}


@router.post("/{proposal_id}/assign-sme")
def assign_sme(proposal_id: str, req: AssignSmeRequest, db: Session = Depends(get_db)):
    proposal = db.scalar(select(Proposal).where(Proposal.id == proposal_id))
    if not proposal:
        raise HTTPException(404, "Proposal not found")

    # Get routing rules for this rfp_type
    rules = db.scalars(
        select(SmeRoutingRule)
        .where(SmeRoutingRule.rfp_type == req.rfp_type)
        .order_by(SmeRoutingRule.priority)
    ).all()

    required_skills = req.required_skills or [r.required_expertise for r in rules]

    # Find available SMEs
    all_smes = db.scalars(
        select(Stakeholder).where(Stakeholder.role == "sme")
    ).all()

    def score_sme(sme: Stakeholder) -> int:
        expertise = sme.expertise or []
        overlap = sum(1 for s in required_skills if s in expertise)
        workload_penalty = sme.current_workload * 2
        return overlap * 10 - workload_penalty

    available = [s for s in all_smes if s.current_workload < 4]
    ranked = sorted(available, key=score_sme, reverse=True)[:3]

    if not ranked:
        raise HTTPException(422, "No available SMEs for this RFP type")

    # Assign top SME
    top_sme = ranked[0]
    sla = db.get(SlaConfig, "sme_assignment")
    due = datetime.utcnow() + timedelta(hours=sla.hours_allowed) if sla else None

    assignment = Assignment(
        proposal_id=proposal.id,
        stakeholder_id=top_sme.id,
        role="sme",
        bu=top_sme.bu,
        status="pending",
        due_at=due,
    )
    db.add(assignment)
    top_sme.current_workload += 1

    db.add(AuditLog(
        entity_type="proposal",
        entity_id=proposal.id,
        action="sme_assigned",
        to_state=proposal.stage,
        meta={"sme_id": top_sme.id, "sme_name": top_sme.name},
    ))

    _add_activity(
        db, proposal.id, "System", "sme_assigned",
        f"SME auto-assigned: {req.rfp_type} → {top_sme.name}",
    )

    db.commit()

    return {
        "assigned": {"id": top_sme.id, "name": top_sme.name, "bu": top_sme.bu},
        "alternatives": [{"id": s.id, "name": s.name, "workload": s.current_workload} for s in ranked[1:]],
    }


@router.get("/{proposal_id}/approvals")
def get_approvals(proposal_id: str, db: Session = Depends(get_db)):
    from models.approval import Approval
    approvals = db.scalars(
        select(Approval)
        .where(Approval.proposal_id == proposal_id)
        .options(joinedload(Approval.approver))
        .order_by(Approval.order_index)
    ).all()

    return [
        {
            "id": a.id,
            "stage": a.stage,
            "order_index": a.order_index,
            "parallel_group": a.parallel_group,
            "status": a.status,
            "decision_note": a.decision_note,
            "decided_at": a.decided_at.isoformat() if a.decided_at else None,
            "due_at": a.due_at.isoformat() if a.due_at else None,
            "approver": {
                "id": a.approver.id,
                "name": a.approver.name,
                "role": a.approver.role,
            } if a.approver else None,
        }
        for a in approvals
    ]
