from datetime import datetime
from temporalio import activity
from sqlalchemy import select

from db.database import SessionLocal
from models import Stakeholder, AuditLog, ActivityFeed
from models.approval import Approval
from temporal.schemas import ApprovalActivityInput


@activity.defn
def persist_approval_decision(input: ApprovalActivityInput) -> dict:
    """
    Persist an approval decision: update status, write audit + activity records.
    Called by workflow after receiving a submit_review signal.
    """
    db = SessionLocal()
    try:
        approval = db.scalar(select(Approval).where(Approval.id == input.approval_id))
        if not approval:
            raise ValueError(f"Approval {input.approval_id} not found")

        approval.status = input.status
        approval.decision_note = input.decision_note
        approval.decided_at = datetime.utcnow()

        actor_name = "Temporal"
        if input.actor_id:
            actor = db.get(Stakeholder, input.actor_id)
            if actor:
                actor_name = actor.name

        db.add(AuditLog(
            entity_type="approval",
            entity_id=input.approval_id,
            actor_id=input.actor_id,
            action=f"approval_{input.status}",
            from_state="pending",
            to_state=input.status,
            meta={"note": input.decision_note or "", "orchestrated_by": "temporal"},
        ))
        db.add(ActivityFeed(
            proposal_id=input.proposal_id,
            actor_name=actor_name,
            action_type="approval_decision",
            description=f"{actor_name} {input.status} {input.stage or 'approval'}",
            is_alert=(input.status == "rejected"),
        ))
        db.commit()
        return {"approval_id": input.approval_id, "status": input.status}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
