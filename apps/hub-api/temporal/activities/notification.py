import json
import logging
from datetime import datetime
from temporalio import activity

from db.database import SessionLocal
from models import ActivityFeed, AuditLog
from temporal.schemas import EventInput, EscalationInput

logger = logging.getLogger("temporal.activities.notification")


@activity.defn
def emit_workflow_event(input: EventInput) -> None:
    """
    Publish a domain event to Redis.
    Degrades silently if Redis is unavailable — never fails the workflow.
    """
    try:
        from events.redis_client import sync_client, EVENTS_CHANNEL
        if sync_client is None:
            return
        payload = json.dumps({
            "event_type": input.event_type,
            "entity_id": input.entity_id,
            "entity_type": input.entity_type,
            "metadata": input.metadata,
            "actor_id": input.actor_id,
            "correlation_id": input.correlation_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
        sync_client.publish(EVENTS_CHANNEL, payload)
    except Exception as exc:
        logger.warning("Failed to emit %s: %s", input.event_type, exc)


@activity.defn
def escalate_sla(input: EscalationInput) -> None:
    """
    Record an SLA breach escalation in the database.
    Temporal ensures this fires exactly once (with retries on transient errors).
    """
    db = SessionLocal()
    try:
        db.add(ActivityFeed(
            proposal_id=input.proposal_id,
            actor_name="Temporal SLA Monitor",
            action_type="sla_escalation",
            description=(
                f"SLA breached in {input.stage} — escalating to "
                f"{input.escalate_to_role or 'presales_lead'}."
            ),
            is_alert=True,
        ))
        db.add(AuditLog(
            entity_type="opportunity",
            entity_id=input.opportunity_id,
            action="sla_escalation",
            to_state=input.stage,
            meta={
                "overdue_hours": input.overdue_hours,
                "escalate_to_role": input.escalate_to_role,
                "correlation_id": input.correlation_id,
                "orchestrated_by": "temporal",
            },
        ))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
