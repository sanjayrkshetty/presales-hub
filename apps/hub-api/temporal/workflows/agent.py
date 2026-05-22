"""Temporal workflow for multi-agent orchestration with human checkpoints."""
from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal.schemas import AgentTaskInput, AgentTaskResult, AgentPlanInput


@workflow.defn
class AgentOrchestratorWorkflow:
    """
    Executes a single agent task with optional human approval checkpoint.

    Signals:
      - approve(task_id): Human approves the pending result
      - reject(task_id): Human rejects; workflow fails
      - cancel(): Cancel in-flight workflow

    Queries:
      - get_status(): Returns current status dict
    """

    def __init__(self) -> None:
        self._approved: bool = False
        self._rejected: bool = False
        self._cancelled: bool = False
        self._approved_task_id: str = ""
        self._result: AgentTaskResult | None = None

    @workflow.run
    async def run(self, inp: AgentTaskInput) -> AgentTaskResult:
        from temporal.activities.agent import execute_agent_task, persist_agent_result

        retry = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=5))

        self._result = await workflow.execute_activity(
            execute_agent_task,
            inp,
            start_to_close_timeout=timedelta(seconds=300),
            retry_policy=retry,
        )

        if self._result.requires_human_review:
            workflow.logger.info(
                "Agent %s waiting for human approval (task_id=%s)",
                inp.agent_type,
                self._result.task_id,
            )
            await workflow.wait_condition(
                lambda: self._approved or self._rejected or self._cancelled,
                timeout=timedelta(hours=24),
            )

            if self._cancelled:
                self._result.status = "cancelled"
                return self._result

            if self._rejected:
                self._result.status = "rejected"
                return self._result

            self._result.status = "completed"

        await workflow.execute_activity(
            persist_agent_result,
            self._result,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        return self._result

    @workflow.signal
    def approve(self, task_id: str) -> None:
        self._approved = True
        self._approved_task_id = task_id

    @workflow.signal
    def reject(self, task_id: str) -> None:
        self._rejected = True

    @workflow.signal
    def cancel(self) -> None:
        self._cancelled = True

    @workflow.query
    def get_status(self) -> dict:
        return {
            "approved": self._approved,
            "rejected": self._rejected,
            "cancelled": self._cancelled,
            "result": {
                "task_id": self._result.task_id if self._result else None,
                "status": self._result.status if self._result else "in_progress",
            },
        }


@workflow.defn
class AgentPlanWorkflow:
    """Executes a named plan (sequence of agent tasks) via AgentOrchestratorWorkflow child workflows."""

    @workflow.run
    async def run(self, inp: AgentPlanInput) -> list[AgentTaskResult]:
        from agent_engine.planners.task_planner import build_plan

        contracts = build_plan(
            plan_name=inp.plan_name,
            proposal_id=inp.proposal_id,
            opportunity_id=inp.opportunity_id,
            base_input=inp.base_input,
        )

        results: list[AgentTaskResult] = []
        for contract in contracts:
            task_inp = AgentTaskInput(
                agent_type=contract.agent_type,
                input_data=contract.input_data,
                proposal_id=contract.proposal_id,
                opportunity_id=contract.opportunity_id,
                requires_approval=contract.requires_approval,
                authority_level=contract.authority_level,
                correlation_id=contract.correlation_id,
            )
            result = await workflow.execute_child_workflow(
                AgentOrchestratorWorkflow.run,
                task_inp,
                id=f"agent-{contract.agent_type}-{contract.task_id}",
                task_queue="presales-hub",
            )
            results.append(result)
            if result.status == "failed":
                workflow.logger.error("Plan halted at %s: %s", contract.agent_type, result.error)
                break

        return results
