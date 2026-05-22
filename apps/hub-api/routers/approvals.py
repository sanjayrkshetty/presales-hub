from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.database import get_db
from events.bus import publish
from events.schema import ApprovalDecisionEvent
from models import AuditLog, ActivityFeed, Stakeholder
from models.approval import Approval

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class DecisionRequest(BaseModel):
    status: str  # approved | rejected | escalated | bypassed
    decision_note: str | None = None
    actor_id: str | None = None


@router.post("/{approval_id}/decide")
def decide(approval_id: str, req: DecisionRequest, db: Session = Depends(get_db)):
    if req.status not in ("approved", "rejected", "escalated", "bypassed"):
        raise HTTPException(422, "status must be: approved | rejected | escalated | bypassed")

    approval = db.scalar(select(Approval).where(Approval.id == approval_id))
    if not approval:
        raise HTTPException(404, "Approval not found")

    if approval.status not in ("pending", "escalated"):
        raise HTTPException(422, f"Approval already finalized: {approval.status}")

    # B1: Authorization — if both actor and assigned approver are known, they must match.
    # System-driven decisions (no actor_id) and unassigned approvals (no approver_id) are allowed.
    if req.actor_id and approval.approver_id and req.actor_id != str(approval.approver_id):
        db.add(AuditLog(
            entity_type="approval",
            entity_id=approval.id,
            actor_id=req.actor_id,
            action="unauthorized_approval_attempt",
            from_state=approval.status,
            to_state=req.status,
            meta={
                "reason": f"actor {req.actor_id} is not the assigned approver {approval.approver_id}",
                "stage": approval.stage,
            },
        ))
        db.commit()
        raise HTTPException(
            403,
            "Not authorized: you are not the assigned approver for this decision. "
            "Unauthorized attempt has been logged."
        )

    approval.status = req.status
    approval.decision_note = req.decision_note
    approval.decided_at = datetime.utcnow()

    actor_name = "System"
    if req.actor_id:
        actor = db.get(Stakeholder, req.actor_id)
        if actor:
            actor_name = actor.name

    db.add(AuditLog(
        entity_type="approval",
        entity_id=approval.id,
        actor_id=req.actor_id,
        action=f"approval_{req.status}",
        from_state="pending",
        to_state=req.status,
        meta={"note": req.decision_note or ""},
    ))

    db.add(ActivityFeed(
        proposal_id=approval.proposal_id,
        actor_name=actor_name,
        action_type="approval_decision",
        description=f"{actor_name} {req.status} {approval.stage or 'approval'}",
        is_alert=(req.status == "rejected"),
    ))

    db.commit()
    publish(ApprovalDecisionEvent(
        entity_id=approval_id,
        actor_id=req.actor_id,
        proposal_id=approval.proposal_id,
        stage=approval.stage,
        status=req.status,
    ))
    return {"approval_id": approval_id, "status": req.status}
