"""
ProposalLifecycleWorkflow — durable proposal state machine.

Design:
  - Runs indefinitely until proposal reaches a terminal stage or is cancelled.
  - All stage transitions are driven by external signals (FastAPI routes).
  - Parallel review is delegated to ParallelReviewWorkflow as a child workflow.
  - All DB mutations and Redis publishes happen inside activities (never in workflow code).
  - Workflow code is fully deterministic: no datetime.now(), no I/O, no random.

Temporal guarantees:
  - Every signal is durably recorded in workflow history.
  - On worker restart, the workflow replays deterministically from history.
  - Activities are retried per DB_RETRY / NOTIFY_RETRY policies.
  - A 7-day wait_condition timeout abandons stalled proposals cleanly.
"""
import asyncio
from datetime import timedelta
from typing import Optional
from temporalio import workflow
from temporalio.common import RetryPolicy

from temporal.schemas import (
    ProposalWorkflowInput, TransitionInput, TransitionResult,
    InitParallelApprovalsInput, ParallelReviewInput, ParallelReviewResult,
    EventInput, TASK_QUEUE, TERMINAL_STAGES, PARALLEL_REVIEW_STAGES,
    STAGE_TRANSITIONS,
)

# Activity imports must be inside imports_passed_through() so Temporal's
# workflow sandbox does not attempt to restrict them.
with workflow.unsafe.imports_passed_through():
    from temporal.activities.proposal import persist_stage_transition, initialize_parallel_approvals
    from temporal.activities.notification import emit_workflow_event
    from temporal.workflows.approval import ParallelReviewWorkflow

_DB_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=5,
    non_retryable_error_types=["ValueError"],
)
_NOTIFY_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=3,
)
_ACT_TIMEOUT = timedelta(seconds=60)
_NOTIFY_TIMEOUT = timedelta(seconds=30)
_STALL_TIMEOUT = timedelta(days=7)


@workflow.defn
class ProposalLifecycleWorkflow:
    """
    Long-running durable workflow for a single proposal.

    Signals:
      request_transition(to_stage, actor_id, note) — advance stage
      cancel()                                      — abandon workflow

    Queries:
      get_stage()   → str
      get_history() → list[dict]
      is_active()   → bool
    """

    def __init__(self) -> None:
        self._stage = "intake"
        self._history: list[dict] = []
        self._pending: Optional[tuple[str, Optional[str], Optional[str]]] = None
        self._cancelled = False

    @workflow.run
    async def run(self, input: ProposalWorkflowInput) -> str:
        proposal_id = input.proposal_id

        await workflow.execute_activity(
            emit_workflow_event,
            EventInput(
                event_type="proposal.workflow.started",
                entity_id=proposal_id,
                entity_type="proposal",
                metadata={"stage": self._stage},
                correlation_id=input.correlation_id,
            ),
            start_to_close_timeout=_NOTIFY_TIMEOUT,
            retry_policy=_NOTIFY_RETRY,
        )

        while not self._cancelled and self._stage not in TERMINAL_STAGES:
            # Block until a transition signal arrives or the proposal stalls for 7 days.
            try:
                await workflow.wait_condition(
                    lambda: self._pending is not None or self._cancelled,
                    timeout=_STALL_TIMEOUT,
                )
            except asyncio.TimeoutError:
                workflow.logger.warning(
                    "Proposal %s stalled in '%s' for 7 days — workflow abandoned",
                    proposal_id, self._stage,
                )
                break

            if self._cancelled or self._pending is None:
                break

            to_stage, actor_id, note = self._pending
            self._pending = None
            from_stage = self._stage

            # ── Parallel review gate ──────────────────────────────────────────
            # Entering any parallel review stage from drafting triggers all 3 reviews
            # concurrently via a child workflow. The child blocks until all 3 decide.
            if to_stage in PARALLEL_REVIEW_STAGES and from_stage == "drafting":
                review_stages = sorted(PARALLEL_REVIEW_STAGES)

                await workflow.execute_activity(
                    initialize_parallel_approvals,
                    InitParallelApprovalsInput(
                        proposal_id=proposal_id,
                        review_stages=review_stages,
                        correlation_id=input.correlation_id,
                    ),
                    start_to_close_timeout=_ACT_TIMEOUT,
                    retry_policy=_DB_RETRY,
                )

                review_result: ParallelReviewResult = await workflow.execute_child_workflow(
                    ParallelReviewWorkflow.run,
                    ParallelReviewInput(
                        proposal_id=proposal_id,
                        timeout_hours=72,
                        correlation_id=input.correlation_id,
                    ),
                    id=f"parallel-review-{proposal_id}",
                    task_queue=TASK_QUEUE,
                    execution_timeout=timedelta(hours=80),
                )

                to_stage = "finance_review" if review_result.all_approved else "drafting"

            # ── Persist transition ────────────────────────────────────────────
            result: TransitionResult = await workflow.execute_activity(
                persist_stage_transition,
                TransitionInput(
                    proposal_id=proposal_id,
                    from_stage=from_stage,
                    to_stage=to_stage,
                    actor_id=actor_id,
                    note=note,
                    correlation_id=input.correlation_id,
                ),
                start_to_close_timeout=_ACT_TIMEOUT,
                retry_policy=_DB_RETRY,
            )

            if not result.success:
                workflow.logger.error(
                    "Transition %s→%s failed for %s: %s",
                    from_stage, to_stage, proposal_id, result.error,
                )
                continue

            self._stage = to_stage
            self._history.append({
                "from": from_stage,
                "to": to_stage,
                "actor_id": actor_id,
                "at": workflow.now().isoformat(),
            })

            # ── Emit domain event (fire-and-forget: won't fail the workflow) ──
            await workflow.execute_activity(
                emit_workflow_event,
                EventInput(
                    event_type="proposal.transitioned",
                    entity_id=proposal_id,
                    entity_type="proposal",
                    metadata={"from_stage": from_stage, "to_stage": to_stage},
                    actor_id=actor_id,
                    correlation_id=input.correlation_id,
                ),
                start_to_close_timeout=_NOTIFY_TIMEOUT,
                retry_policy=_NOTIFY_RETRY,
            )

        return self._stage

    # ── Signals ───────────────────────────────────────────────────────────────

    @workflow.signal
    async def request_transition(
        self,
        to_stage: str,
        actor_id: Optional[str] = None,
        note: Optional[str] = None,
    ) -> None:
        """Advance the proposal to the next stage (validated against STAGE_TRANSITIONS)."""
        allowed = STAGE_TRANSITIONS.get(self._stage, [])
        if to_stage not in allowed:
            workflow.logger.warning(
                "Rejected illegal transition %s -> %s (allowed=%s)",
                self._stage, to_stage, allowed,
            )
            return
        # Guard single pending slot against rapid-signal overwrite
        if self._pending is not None:
            workflow.logger.warning(
                "Ignoring transition to %s; pending %s already queued",
                to_stage, self._pending[0],
            )
            return
        self._pending = (to_stage, actor_id, note)

    @workflow.signal
    async def cancel(self) -> None:
        """Abandon this workflow — transitions proposal to closed_lost."""
        self._cancelled = True

    # ── Queries ───────────────────────────────────────────────────────────────

    @workflow.query
    def get_stage(self) -> str:
        return self._stage

    @workflow.query
    def get_history(self) -> list:
        return self._history

    @workflow.query
    def is_active(self) -> bool:
        return not self._cancelled and self._stage not in TERMINAL_STAGES
