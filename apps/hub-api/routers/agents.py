"""
Multi-Agent Orchestration API.

Agents are bounded specialists — they only recommend/draft/analyze/retrieve.
All state mutations require human approval or go through existing workflow routers.

Endpoints:
  POST /api/agents/tasks                      Submit a single agent task
  GET  /api/agents/tasks/{task_id}            Get task status from in-process memory
  POST /api/agents/tasks/{task_id}/approve    Signal approval (direct, non-Temporal)
  POST /api/agents/tasks/{task_id}/reject     Signal rejection (direct, non-Temporal)
  GET  /api/agents/registry                   List all registered agent types
  POST /api/agents/plans                      Submit a named multi-agent plan
  POST /api/agents/simulate                   Run simulation harness
  GET  /api/agents/health                     Health + config
"""
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from lib.dependencies import require_permission

# Import agent prompt modules to populate registry
import agent_engine.prompts.agent_rfp_analysis        # noqa: F401
import agent_engine.prompts.agent_proposal_drafting   # noqa: F401
import agent_engine.prompts.agent_risk_assessment     # noqa: F401
import agent_engine.prompts.agent_compliance_check    # noqa: F401
import agent_engine.prompts.agent_sme_coordination    # noqa: F401
import agent_engine.prompts.agent_executive_briefing  # noqa: F401
import agent_engine.prompts.agent_approval_reasoning  # noqa: F401
import agent_engine.prompts.agent_solution_architecture  # noqa: F401
import agent_engine.prompts.agent_timeline_planning   # noqa: F401
import agent_engine.prompts.agent_escalation          # noqa: F401

from agent_engine.agents.registry import get_agent, list_agent_types
from agent_engine.execution.task_contract import TaskContract
from agent_engine.guardrails.agent_guardrails import validate_task_contract
from agent_engine.memory.agent_memory import get_agent_memory
from agent_engine.orchestration.agent_orchestrator import AgentOrchestrator
from agent_engine.planners.task_planner import build_plan, list_plans
from agent_engine.simulations.agent_sim import SimulationScenario, run_simulation_suite
from copilot_engine.providers.mock_provider import MockLLMProvider

logger = logging.getLogger("routers.agents")
router = APIRouter(prefix="/api/agents", tags=["agents"])


def _get_provider():
    from copilot_engine.providers.factory import get_llm_provider
    return get_llm_provider()


# ── Request models ─────────────────────────────────────────────────────────────

class SubmitTaskRequest(BaseModel):
    agent_type: str
    input_data: dict[str, Any] = Field(default_factory=dict)
    proposal_id: Optional[str] = None
    opportunity_id: Optional[str] = None


class SubmitPlanRequest(BaseModel):
    plan_name: str
    proposal_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    base_input: dict[str, Any] = Field(default_factory=dict)


class SimulateRequest(BaseModel):
    scenarios: list[dict[str, Any]] = Field(..., min_length=1)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/tasks")
async def submit_task(req: SubmitTaskRequest, db: Session = Depends(get_db), _authz=require_permission("agent:execute")):
    contract = TaskContract(
        agent_type=req.agent_type,
        proposal_id=req.proposal_id,
        opportunity_id=req.opportunity_id,
        input_data=req.input_data,
    )
    safe, violations = validate_task_contract(contract)
    if not safe:
        raise HTTPException(status_code=422, detail={"guardrail_violations": violations})

    try:
        orchestrator = AgentOrchestrator(db=db, provider=_get_provider())
        result = await orchestrator.run(contract)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return result.to_dict()


@router.get("/tasks/{task_id}")
def get_task_status(task_id: str):
    memory = get_agent_memory()
    entry = memory.get(task_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found in memory")
    return {
        "task_id": entry.task_id,
        "agent_type": entry.agent_type,
        "status": entry.status,
        "confidence": entry.confidence,
        "grounding_score": entry.grounding_score,
        "output_summary": entry.output_summary,
        "created_at": entry.created_at.isoformat(),
    }


@router.post("/tasks/{task_id}/approve")
def approve_task(task_id: str, _authz=require_permission("agent:execute")):
    memory = get_agent_memory()
    entry = memory.get(task_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")
    if entry.status != "pending_approval":
        raise HTTPException(status_code=400, detail=f"Task is not pending approval (status={entry.status!r})")
    entry.status = "completed"
    logger.info("Task %s approved by human", task_id)
    return {"task_id": task_id, "status": "completed"}


@router.post("/tasks/{task_id}/reject")
def reject_task(task_id: str, _authz=require_permission("agent:execute")):
    memory = get_agent_memory()
    entry = memory.get(task_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id!r} not found")
    entry.status = "rejected"
    logger.info("Task %s rejected by human", task_id)
    return {"task_id": task_id, "status": "rejected"}


@router.get("/registry")
def list_registry():
    return {"agents": list_agent_types()}


@router.post("/plans")
async def submit_plan(req: SubmitPlanRequest, db: Session = Depends(get_db), _authz=require_permission("agent:execute")):
    try:
        contracts = build_plan(
            plan_name=req.plan_name,
            proposal_id=req.proposal_id,
            opportunity_id=req.opportunity_id,
            base_input=req.base_input,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    orchestrator = AgentOrchestrator(db=db, provider=_get_provider())
    results = await orchestrator.run_plan(contracts)
    return {
        "plan_name": req.plan_name,
        "tasks_submitted": len(contracts),
        "results": [r.to_dict() for r in results],
    }


@router.post("/simulate")
async def simulate(req: SimulateRequest, db: Session = Depends(get_db), _authz=require_permission("agent:execute")):
    scenarios = [
        SimulationScenario(
            name=s.get("name", f"scenario_{i}"),
            agent_type=s["agent_type"],
            input_data=s.get("input_data", {}),
            proposal_id=s.get("proposal_id"),
            opportunity_id=s.get("opportunity_id"),
            expected_status=s.get("expected_status", "completed"),
            expected_fields=s.get("expected_fields"),
        )
        for i, s in enumerate(req.scenarios)
    ]
    provider = MockLLMProvider()
    results = await run_simulation_suite(scenarios, db=db, provider=provider)
    return {
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "results": [
            {
                "scenario": r.scenario_name,
                "agent_type": r.agent_type,
                "status": r.status,
                "passed": r.passed,
                "eval_score": r.eval_score,
                "latency_ms": round(r.latency_ms, 1),
                "errors": r.errors,
            }
            for r in results
        ],
    }


@router.get("/health")
def agents_health():
    from agent_engine.config import (
        AGENT_DEFAULT_TIMEOUT_SECONDS,
        AGENT_MAX_RETRIES,
        AGENT_MAX_TOOL_CALLS,
        APPROVAL_REQUIRED_AGENTS,
    )
    return {
        "status": "ok",
        "agents_registered": len(list_agent_types()),
        "plans_available": [p["plan_name"] for p in list_plans()],
        "config": {
            "default_timeout_s": AGENT_DEFAULT_TIMEOUT_SECONDS,
            "max_retries": AGENT_MAX_RETRIES,
            "max_tool_calls": AGENT_MAX_TOOL_CALLS,
            "approval_required_agents": sorted(APPROVAL_REQUIRED_AGENTS),
        },
    }
