"""
Temporal-aware workflow endpoints.

These endpoints delegate orchestration to Temporal.
The existing /api/proposals/* routes remain for backwards compatibility.

Design:
  POST /api/workflows/proposals/{id}/start      — start ProposalLifecycleWorkflow
  POST /api/workflows/proposals/{id}/transition — signal stage transition
  GET  /api/workflows/proposals/{id}/status     — query current state
  POST /api/workflows/proposals/{id}/cancel     — cancel workflow
  POST /api/workflows/proposals/{id}/reviews/submit  — signal a review decision

All endpoints return 503 when Temporal is unreachable (graceful degradation).
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from temporal.client import get_temporal_client
from lib.dependencies import require_permission
from temporal.schemas import ProposalWorkflowInput, ParallelReviewInput, TASK_QUEUE
from telemetry.context import get_correlation_id, set_proposal_id

logger = logging.getLogger("routers.workflows")

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class StartWorkflowRequest(BaseModel):
    proposal_id: str


class TransitionSignalRequest(BaseModel):
    to_stage: str
    actor_id: Optional[str] = None
    note: Optional[str] = None


class ReviewDecisionRequest(BaseModel):
    stage: str
    status: str  # approved | rejected | escalated
    actor_id: Optional[str] = None
    note: Optional[str] = None


def _require_temporal(client):
    if client is None:
        raise HTTPException(
            503,
            "Temporal orchestration is unavailable. "
            "Ensure Temporal server is running at TEMPORAL_HOST.",
        )


@router.post("/proposals/{proposal_id}/start")
async def start_proposal_workflow(proposal_id: str, _authz=require_permission("proposal:write")):
    """
    Start a durable ProposalLifecycleWorkflow for this proposal.
    Idempotent: returns 409 if the workflow is already running.
    """
    set_proposal_id(proposal_id)
    client = await get_temporal_client()
    _require_temporal(client)

    from temporal.workflows.proposal import ProposalLifecycleWorkflow

    try:
        handle = await client.start_workflow(
            ProposalLifecycleWorkflow.run,
            ProposalWorkflowInput(
                proposal_id=proposal_id,
                correlation_id=get_correlation_id(),
            ),
            id=f"proposal-{proposal_id}",
            task_queue=TASK_QUEUE,
        )
        logger.info("Workflow started: %s", handle.id)
        return {"workflow_id": handle.id, "proposal_id": proposal_id, "status": "started"}
    except Exception as exc:
        if "already" in str(exc).lower():
            raise HTTPException(409, f"Workflow already running for proposal {proposal_id}")
        raise HTTPException(500, str(exc))


@router.post("/proposals/{proposal_id}/transition")
async def signal_transition(proposal_id: str, req: TransitionSignalRequest, _authz=require_permission("proposal:write")):
    """Signal a stage transition into the running workflow."""
    set_proposal_id(proposal_id)
    client = await get_temporal_client()
    _require_temporal(client)

    from temporal.workflows.proposal import ProposalLifecycleWorkflow

    handle = client.get_workflow_handle(f"proposal-{proposal_id}")
    try:
        await handle.signal(
            ProposalLifecycleWorkflow.request_transition,
            args=[req.to_stage, req.actor_id, req.note],
        )
        return {"signaled": True, "to_stage": req.to_stage}
    except Exception as exc:
        raise HTTPException(404, f"No running workflow for proposal {proposal_id}: {exc}")


@router.get("/proposals/{proposal_id}/status")
async def query_workflow_status(proposal_id: str):
    """Query the current stage and transition history from the workflow."""
    client = await get_temporal_client()
    _require_temporal(client)

    from temporal.workflows.proposal import ProposalLifecycleWorkflow

    handle = client.get_workflow_handle(f"proposal-{proposal_id}")
    try:
        stage = await handle.query(ProposalLifecycleWorkflow.get_stage)
        history = await handle.query(ProposalLifecycleWorkflow.get_history)
        is_active = await handle.query(ProposalLifecycleWorkflow.is_active)
        return {
            "workflow_id": f"proposal-{proposal_id}",
            "stage": stage,
            "is_active": is_active,
            "transition_history": history,
        }
    except Exception as exc:
        raise HTTPException(404, f"Workflow not found for proposal {proposal_id}: {exc}")


@router.post("/proposals/{proposal_id}/cancel")
async def cancel_workflow(proposal_id: str, _authz=require_permission("proposal:write")):
    """Cancel the proposal workflow — signals it to stop gracefully."""
    client = await get_temporal_client()
    _require_temporal(client)

    from temporal.workflows.proposal import ProposalLifecycleWorkflow

    handle = client.get_workflow_handle(f"proposal-{proposal_id}")
    try:
        await handle.signal(ProposalLifecycleWorkflow.cancel)
        return {"cancelled": True, "proposal_id": proposal_id}
    except Exception as exc:
        raise HTTPException(404, f"Workflow not found: {exc}")


@router.post("/proposals/{proposal_id}/reviews/submit")
async def submit_review_decision(proposal_id: str, req: ReviewDecisionRequest, _authz=require_permission("approval:approve")):
    """
    Send a review decision into the ParallelReviewWorkflow child workflow.
    The child workflow ID is deterministically derived from proposal_id.
    """
    set_proposal_id(proposal_id)
    client = await get_temporal_client()
    _require_temporal(client)

    from temporal.workflows.approval import ParallelReviewWorkflow

    handle = client.get_workflow_handle(f"parallel-review-{proposal_id}")
    try:
        await handle.signal(
            ParallelReviewWorkflow.submit_review,
            args=[req.stage, req.status, req.actor_id, req.note],
        )
        return {"signaled": True, "stage": req.stage, "status": req.status}
    except Exception as exc:
        raise HTTPException(
            404,
            f"No parallel review workflow found for proposal {proposal_id}: {exc}",
        )


@router.post("/proposals/{proposal_id}/sla/resolve")
async def resolve_sla(proposal_id: str, stage: str, _authz=require_permission("proposal:write")):
    """
    Signal the SlaEscalationWorkflow that the proposal has advanced,
    disarming the SLA timer before it fires.
    Workflow ID is deterministically derived from (proposal_id, stage).
    """
    client = await get_temporal_client()
    _require_temporal(client)

    from temporal.workflows.sla import SlaEscalationWorkflow

    handle = client.get_workflow_handle(f"sla-{proposal_id}-{stage}")
    try:
        await handle.signal(SlaEscalationWorkflow.resolve)
        return {"resolved": True, "stage": stage}
    except Exception as exc:
        raise HTTPException(404, f"SLA workflow not found for {proposal_id}/{stage}: {exc}")
