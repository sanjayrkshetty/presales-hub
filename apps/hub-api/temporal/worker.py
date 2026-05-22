"""
Temporal worker process for PRESALES HUB.

Run alongside the API (separate process):
    cd apps/hub-api
    python -m temporal.worker

Or via docker-compose (see docker-compose.dev.yml).

The worker connects to the Temporal server, registers all workflows and
activities, and polls the task queue for work. It runs until killed.
"""
import asyncio
import logging
import os
import sys

# Ensure hub-api is on the path when run as a module from any directory.
_here = os.path.dirname(os.path.abspath(__file__))
_api_root = os.path.dirname(_here)
if _api_root not in sys.path:
    sys.path.insert(0, _api_root)

from telemetry import setup_logging

setup_logging()
logger = logging.getLogger("temporal.worker")

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")


async def main() -> None:
    from temporalio.client import Client
    from temporalio.worker import Worker

    from temporal.schemas import TASK_QUEUE
    from temporal.workflows.proposal import ProposalLifecycleWorkflow
    from temporal.workflows.approval import ParallelReviewWorkflow
    from temporal.workflows.sla import SlaEscalationWorkflow
    from temporal.workflows.agent import AgentOrchestratorWorkflow, AgentPlanWorkflow
    from temporal.activities.proposal import persist_stage_transition, initialize_parallel_approvals
    from temporal.activities.approval import persist_approval_decision
    from temporal.activities.notification import emit_workflow_event, escalate_sla
    from temporal.activities.agent import execute_agent_task, persist_agent_result

    logger.info("Connecting to Temporal at %s", TEMPORAL_HOST)
    client = await Client.connect(TEMPORAL_HOST)

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[
            ProposalLifecycleWorkflow,
            ParallelReviewWorkflow,
            SlaEscalationWorkflow,
            AgentOrchestratorWorkflow,
            AgentPlanWorkflow,
        ],
        activities=[
            persist_stage_transition,
            initialize_parallel_approvals,
            persist_approval_decision,
            emit_workflow_event,
            escalate_sla,
            execute_agent_task,
            persist_agent_result,
        ],
    )

    logger.info("Temporal worker running on task queue '%s'", TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
