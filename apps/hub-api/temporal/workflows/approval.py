"""
ParallelReviewWorkflow — concurrent 3-way review coordination.

Spawned as a child workflow by ProposalLifecycleWorkflow when the proposal
enters the parallel review stage. Waits for all three reviewers
(technical, security, delivery) to decide within the timeout window.

On timeout, pending reviews are auto-escalated and the parent workflow
is notified to return the proposal to drafting.

Signals:
  submit_review(stage, status, actor_id, note) — individual review decision

Queries:
  get_decisions()  → dict[stage, {status, actor_id}]
  is_complete()    → bool — True when all 3 reviews decided
"""
import asyncio
from datetime import timedelta
from typing import Optional
from temporalio import workflow
from temporalio.common import RetryPolicy

from temporal.schemas import (
    ParallelReviewInput, ParallelReviewResult, ReviewDecision,
    EventInput, PARALLEL_REVIEW_STAGES,
)

with workflow.unsafe.imports_passed_through():
    from temporal.activities.notification import emit_workflow_event

_NOTIFY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=3,
)


@workflow.defn
class ParallelReviewWorkflow:
    def __init__(self) -> None:
        self._decisions: dict[str, ReviewDecision] = {}

    @workflow.run
    async def run(self, input: ParallelReviewInput) -> ParallelReviewResult:
        required = sorted(PARALLEL_REVIEW_STAGES)

        try:
            await workflow.wait_condition(
                lambda: all(s in self._decisions for s in required),
                timeout=timedelta(hours=input.timeout_hours),
            )
        except asyncio.TimeoutError:
            pending = [s for s in required if s not in self._decisions]
            workflow.logger.warning(
                "Parallel review timed out for %s — pending: %s",
                input.proposal_id, pending,
            )
            for stage in pending:
                await workflow.execute_activity(
                    emit_workflow_event,
                    EventInput(
                        event_type="approval.timeout",
                        entity_id=input.proposal_id,
                        entity_type="proposal",
                        metadata={"stage": stage, "timeout_hours": input.timeout_hours},
                        correlation_id=input.correlation_id,
                    ),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=_NOTIFY_RETRY,
                )
                self._decisions[stage] = ReviewDecision(
                    stage=stage,
                    status="escalated",
                    note=f"Auto-escalated: no decision within {input.timeout_hours}h",
                )

        all_approved = all(
            self._decisions.get(s, ReviewDecision(stage=s, status="pending")).status == "approved"
            for s in required
        )

        return ParallelReviewResult(
            all_approved=all_approved,
            decisions={
                s: {"status": d.status, "actor_id": d.actor_id, "note": d.note}
                for s, d in self._decisions.items()
            },
        )

    @workflow.signal
    async def submit_review(
        self,
        stage: str,
        status: str,
        actor_id: Optional[str] = None,
        note: Optional[str] = None,
    ) -> None:
        """Called by the approvals router when a reviewer decides."""
        self._decisions[stage] = ReviewDecision(
            stage=stage, status=status, actor_id=actor_id, note=note
        )

    @workflow.query
    def get_decisions(self) -> dict:
        return {
            s: {"status": d.status, "actor_id": d.actor_id}
            for s, d in self._decisions.items()
        }

    @workflow.query
    def is_complete(self) -> bool:
        return all(s in self._decisions for s in sorted(PARALLEL_REVIEW_STAGES))
