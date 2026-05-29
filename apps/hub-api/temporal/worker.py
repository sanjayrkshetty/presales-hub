"""
Temporal worker process for PRESALES HUB.

Run alongside the API (separate process):
    cd apps/hub-api
    python -m temporal.worker

Or via docker-compose (see docker-compose.full.yml — temporal-worker service).

Health endpoint: GET http://localhost:8004/health
"""
import asyncio
import concurrent.futures
import json
import logging
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

_here = os.path.dirname(os.path.abspath(__file__))
_api_root = os.path.dirname(_here)
if _api_root not in sys.path:
    sys.path.insert(0, _api_root)

from telemetry import setup_logging

setup_logging()
logger = logging.getLogger("temporal.worker")

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
HEALTH_PORT = int(os.getenv("WORKER_HEALTH_PORT", "8004"))

_shutdown_event: asyncio.Event | None = None

REGISTERED_WORKFLOWS = [
    "ProposalLifecycleWorkflow",
    "ParallelReviewWorkflow",
    "SlaEscalationWorkflow",
    "AgentOrchestratorWorkflow",
    "AgentPlanWorkflow",
]

REGISTERED_ACTIVITIES = [
    "persist_stage_transition",
    "initialize_parallel_approvals",
    "persist_approval_decision",
    "emit_workflow_event",
    "escalate_sla",
    "execute_agent_task",
    "persist_agent_result",
]


def _make_health_handler():
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({
                    "status": "ok",
                    "workflows": REGISTERED_WORKFLOWS,
                    "activities": REGISTERED_ACTIVITIES,
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # suppress HTTP access log noise

    return HealthHandler


def _start_health_server() -> None:
    server = HTTPServer(("", HEALTH_PORT), _make_health_handler())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info("Worker health endpoint on port %d", HEALTH_PORT)


async def main() -> None:
    global _shutdown_event
    _shutdown_event = asyncio.Event()

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

    loop = asyncio.get_running_loop()

    def _handle_signal(*_):
        logger.info("Shutdown signal received — draining in-flight activities")
        loop.call_soon_threadsafe(_shutdown_event.set)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    _start_health_server()

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
        activity_executor=concurrent.futures.ThreadPoolExecutor(max_workers=10),
    )

    logger.info("Temporal worker running on task queue '%s'", TASK_QUEUE)
    async with worker:
        await _shutdown_event.wait()

    logger.info("Temporal worker stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())
