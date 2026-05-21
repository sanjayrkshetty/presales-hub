from datetime import datetime, timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from db.database import get_db
from models import Proposal, Stakeholder, Assignment, ActivityFeed, AuditLog, SlaConfig, SmeRoutingRule
from models.proposal import TRANSITIONS, PARALLEL_REVIEW_GROUP
from models.approval import Approval

router = APIRouter(prefix="/api/proposals", tags=["proposals"])

# Maps each review/approval stage to the stakeholder role responsible for signing off
STAGE_REVIEWER_ROLE: dict[str, str] = {
    "technical_review": "solution_architect",
    "security_review":  "security_reviewer",
    "delivery_review":  "solution_architect",
    "finance_review":   "finance",
    "legal_review":     "legal",
    "approval":         "presales_lead",
}


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


def _find_reviewer(db: Session, role: str) -> Stakeholder | None:
    return db.scalar(select(Stakeholder).where(Stakeholder.role == role))


@router.post("/{proposal_id}/transition")
def transition_proposal(proposal_id: str, req: TransitionRequest, db: Session = Depends(get_db)):
    proposal = db.scalar(select(Proposal).where(Proposal.id == proposal_id))
    if not proposal:
        raise HTTPException(404, "Proposal not found")

    # Validate stage transition is in the allowed graph
    allowed = TRANSITIONS.get(proposal.stage, [])
    if req.to_stage not in allowed:
        raise HTTPException(422, f"Invalid transition: {proposal.stage} → {req.to_stage}. Allowed: {allowed}")

    # B2: Gate — exiting any parallel review to finance_review requires ALL 3 completed
    if proposal.stage in PARALLEL_REVIEW_GROUP and req.to_stage == "finance_review":
        parallel_approvals = [a for a in proposal.approvals if a.stage in PARALLEL_REVIEW_GROUP]
        if len(parallel_approvals) < len(PARALLEL_REVIEW_GROUP):
            missing = sorted(PARALLEL_REVIEW_GROUP - {a.stage for a in parallel_approvals})
            raise HTTPException(
                422,
                f"Parallel review approvals not yet initialized for: {missing}. "
                f"Transition into a review stage first to initialize all 3 approval records."
            )
        incomplete = sorted(a.stage for a in parallel_approvals if a.status != "approved")
        if incomplete:
            raise HTTPException(
                422,
                f"Cannot advance to finance_review: reviews still pending in {incomplete}. "
                f"All three parallel reviews (technical, security, delivery) must be approved."
            )

    # B13 (architectural fix): entering any parallel review stage initializes Approval records
    # for ALL 3 stages via role-based routing. These are review approvals, not SME assignments.
    if req.to_stage in PARALLEL_REVIEW_GROUP and proposal.stage == "drafting":
        existing_stages = {a.stage for a in proposal.approvals}
        for review_stage in sorted(PARALLEL_REVIEW_GROUP):
            if review_stage not in existing_stages:
                reviewer_role = STAGE_REVIEWER_ROLE.get(review_stage)
                reviewer = _find_reviewer(db, reviewer_role) if reviewer_role else None
                sla = db.get(SlaConfig, review_stage)
                due = datetime.utcnow() + timedelta(hours=sla.hours_allowed) if sla else None
                db.add(Approval(
                    proposal_id=proposal.id,
                    approver_id=reviewer.id if reviewer else None,
                    stage=review_stage,
                    parallel_group="review_round_1",
                    order_index=0,
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

    # B11: Guard unknown RFP type — never silently assign a random SME
    if not rules and not req.required_skills:
        raise HTTPException(
            404,
            f"No routing rules found for RFP type: '{req.rfp_type}'. "
            f"Add routing rules to sme_routing_rules or provide required_skills explicitly."
        )

    required_skills = req.required_skills or [r.required_expertise for r in rules]

    # Find available SMEs (role=sme) and solution architects who are within workload limit
    ASSIGNABLE_ROLES = ("sme", "solution_architect", "security_reviewer")
    all_candidates = db.scalars(
        select(Stakeholder).where(Stakeholder.role.in_(ASSIGNABLE_ROLES))
    ).all()

    def score_sme(sme: Stakeholder) -> int:
        expertise = sme.expertise or []
        overlap = sum(1 for s in required_skills if s in expertise)
        workload_penalty = sme.current_workload * 2
        return overlap * 10 - workload_penalty

    available = [s for s in all_candidates if s.current_workload < 4]
    if not available:
        raise HTTPException(422, "All SMEs and solution architects are at maximum workload capacity")

    ranked = sorted(available, key=score_sme, reverse=True)[:3]

    # Assign top scorer
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
