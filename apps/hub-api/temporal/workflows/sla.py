"""
SlaEscalationWorkflow — durable SLA timer using Temporal's scheduler.

Started when a proposal enters a stage with an SLA. Sleeps for exactly
sla_hours using Temporal's durable timer (survives worker restarts).
If the proposal advances before the timer fires, a 'resolve' signal
cancels the escalation path.

Signals:
  resolve() — proposal has moved on; no escalation needed

Queries:
  is_resolved() → bool
"""
import asyncio
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

from temporal.schemas import SlaInput, EscalationInput, EventInput

with workflow.unsafe.imports_passed_through():
    from temporal.activities.notification import emit_workflow_event, escalate_sla

_ESCALATION_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=10),
    maximum_attempts=5,
)


@workflow.defn
class SlaEscalationWorkflow:
    def __init__(self) -> None:
        self._resolved = False

    @workflow.run
    async def run(self, input: SlaInput) -> dict:
        try:
            # Durable timer — survives worker restarts and server reboots.
            # Temporal records the timer in workflow history so it fires
            # exactly once, even after replay.
            await workflow.wait_condition(
                lambda: self._resolved,
                timeout=timedelta(hours=input.sla_hours),
            )
            return {"breached": False, "stage": input.stage, "proposal_id": input.proposal_id}
        except asyncio.TimeoutError:
            pass

        # SLA breached — persist escalation record and emit breach event.
        workflow.logger.warning(
            "SLA breach: proposal=%s stage=%s sla_hours=%d",
            input.proposal_id, input.stage, input.sla_hours,
        )

        await workflow.execute_activity(
            escalate_sla,
            EscalationInput(
                proposal_id=input.proposal_id,
                opportunity_id=input.opportunity_id,
                stage=input.stage,
                escalate_to_role=input.escalate_to_role,
                overdue_hours=0.0,
                correlation_id=input.correlation_id,
            ),
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=_ESCALATION_RETRY,
        )

        await workflow.execute_activity(
            emit_workflow_event,
            EventInput(
                event_type="sla.breach",
                entity_id=input.opportunity_id,
                entity_type="opportunity",
                metadata={
                    "stage": input.stage,
                    "sla_hours": input.sla_hours,
                    "proposal_id": input.proposal_id,
                    "escalate_to_role": input.escalate_to_role,
                },
                correlation_id=input.correlation_id,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_ESCALATION_RETRY,
        )

        return {"breached": True, "stage": input.stage, "proposal_id": input.proposal_id}

    @workflow.signal
    async def resolve(self) -> None:
        """Proposal advanced out of this stage — disarm the escalation timer."""
        self._resolved = True

    @workflow.query
    def is_resolved(self) -> bool:
        return self._resolved
