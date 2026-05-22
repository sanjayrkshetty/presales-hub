"""Temporal activities for agent task execution."""
from __future__ import annotations

import logging
import os

from temporalio import activity

from temporal.schemas import AgentTaskInput, AgentTaskResult

logger = logging.getLogger(__name__)


@activity.defn
async def execute_agent_task(inp: AgentTaskInput) -> AgentTaskResult:
    from database import SessionLocal
    from agent_engine.execution.task_contract import TaskContract
    from agent_engine.orchestration.agent_orchestrator import AgentOrchestrator
    from copilot_engine.providers.factory import get_llm_provider

    db = SessionLocal()
    try:
        provider = get_llm_provider()
        orchestrator = AgentOrchestrator(db=db, provider=provider)
        contract = TaskContract(
            agent_type=inp.agent_type,
            proposal_id=inp.proposal_id,
            opportunity_id=inp.opportunity_id,
            input_data=inp.input_data,
            requires_approval=inp.requires_approval,
            authority_level=inp.authority_level,
            correlation_id=inp.correlation_id,
        )
        result = await orchestrator.run(contract)
        return AgentTaskResult(
            task_id=result.task_id,
            agent_type=result.agent_type,
            status=result.status,
            output=result.output,
            confidence=result.confidence,
            grounding_score=result.grounding_score,
            tools_used=result.tools_used,
            tokens_used=result.tokens_used,
            latency_ms=result.latency_ms,
            requires_human_review=result.requires_human_review,
            error=result.error,
        )
    finally:
        db.close()


@activity.defn
async def persist_agent_result(result: AgentTaskResult) -> bool:
    logger.info(
        "Agent %s task %s completed with status=%s confidence=%.2f",
        result.agent_type,
        result.task_id,
        result.status,
        result.confidence,
    )
    return True
