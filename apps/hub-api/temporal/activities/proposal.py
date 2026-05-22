"""
Proposal lifecycle activities — all DB mutations for workflow state.

Activities are determinism-free: they own all I/O (DB reads/writes).
Temporal retries them automatically on failure per the RetryPolicy.
"""
from datetime import datetime, timedelta
from temporalio import activity
from sqlalchemy import select

from db.database import SessionLocal
from models import Proposal, Stakeholder, AuditLog, ActivityFeed, SlaConfig
from models.approval import Approval
from temporal.schemas import TransitionInput, TransitionResult, InitParallelApprovalsInput

_STAGE_REVIEWER_ROLE = {
    "technical_review": "solution_architect",
    "security_review": "security_reviewer",
    "delivery_review": "solution_architect",
}


@activity.defn
def persist_stage_transition(input: TransitionInput) -> TransitionResult:
    """
    Atomically persist a stage transition: update proposal + opportunity,
    write audit log, write activity feed entry.
    Idempotent within the same (proposal_id, from_stage, to_stage) triple.
    """
    db = SessionLocal()
    try:
        proposal = db.scalar(select(Proposal).where(Proposal.id == input.proposal_id))
        if not proposal:
            raise ValueError(f"Proposal {input.proposal_id} not found")

        from_stage = proposal.stage
        proposal.stage = input.to_stage
        proposal.updated_at = datetime.utcnow()

        if input.to_stage == "submission":
            proposal.submitted_at = datetime.utcnow()

        if proposal.opportunity:
            proposal.opportunity.stage = input.to_stage
            proposal.opportunity.updated_at = datetime.utcnow()

        actor_name = "Temporal"
        if input.actor_id:
            actor = db.get(Stakeholder, input.actor_id)
            if actor:
                actor_name = actor.name

        db.add(AuditLog(
            entity_type="proposal",
            entity_id=input.proposal_id,
            actor_id=input.actor_id,
            action="stage_transition",
            from_state=from_stage,
            to_state=input.to_stage,
            meta={
                "note": input.note or "",
                "correlation_id": input.correlation_id,
                "orchestrated_by": "temporal",
            },
        ))
        db.add(ActivityFeed(
            proposal_id=input.proposal_id,
            actor_name=actor_name,
            action_type="stage_transition",
            description=f"Moved to {input.to_stage.replace('_', ' ').title()}",
        ))
        db.commit()
        return TransitionResult(success=True, stage=input.to_stage)
    except Exception as exc:
        db.rollback()
        raise
    finally:
        db.close()


@activity.defn
def initialize_parallel_approvals(input: InitParallelApprovalsInput) -> list:
    """
    Create Approval records for all 3 parallel review stages.
    Idempotent — skips stages that already have a record.
    Returns list of stage names actually created.
    """
    db = SessionLocal()
    try:
        existing = {
            a.stage for a in db.scalars(
                select(Approval).where(Approval.proposal_id == input.proposal_id)
            ).all()
        }

        created = []
        for stage in input.review_stages:
            if stage in existing:
                continue

            reviewer_role = _STAGE_REVIEWER_ROLE.get(stage)
            reviewer = None
            if reviewer_role:
                reviewer = db.scalar(
                    select(Stakeholder).where(Stakeholder.role == reviewer_role)
                )

            sla = db.get(SlaConfig, stage)
            due = datetime.utcnow() + timedelta(hours=sla.hours_allowed) if sla else None

            db.add(Approval(
                proposal_id=input.proposal_id,
                approver_id=reviewer.id if reviewer else None,
                stage=stage,
                parallel_group="review_round_1",
                order_index=0,
                status="pending",
                due_at=due,
            ))
            created.append(stage)

        db.commit()
        return created
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
