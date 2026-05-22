from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agent_engine.agents.registry import get_agent
from agent_engine.evaluators.agent_evaluator import evaluate_result
from agent_engine.execution.task_contract import AgentResult, TaskContract
from agent_engine.guardrails.agent_guardrails import validate_agent_output, validate_task_contract
from agent_engine.memory.agent_memory import get_agent_memory
from agent_engine.policies.authority import requires_human_approval
from agent_engine.tools.approval_tools import FetchApprovalHistoryTool, FetchApprovalTool
from agent_engine.tools.analytics_tools import ComputeWinRateTool, SummarizeOpportunityMetricsTool
from agent_engine.tools.document_tools import ExtractRFPRequirementsTool, SummarizeDocumentTool
from agent_engine.tools.memory_tools import FetchSimilarProposalsTool, SearchMemoryTool
from agent_engine.tools.proposal_tools import FetchProposalTool, ListProposalSectionsTool
from agent_engine.tools.risk_tools import AssessProposalRiskTool, FetchComplianceRequirementsTool
from agent_engine.tools.sme_tools import ListSMEsTool, MatchSMEToRequirementsTool
from agent_engine.tools.workflow_tools import FetchWorkflowStateTool, ListPendingApprovalsTool

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from copilot_engine.providers.base import LLMProvider

logger = logging.getLogger(__name__)

_ALL_TOOLS = [
    FetchProposalTool(),
    ListProposalSectionsTool(),
    FetchWorkflowStateTool(),
    ListPendingApprovalsTool(),
    ListSMEsTool(),
    MatchSMEToRequirementsTool(),
    SearchMemoryTool(),
    FetchSimilarProposalsTool(),
    ComputeWinRateTool(),
    SummarizeOpportunityMetricsTool(),
    FetchApprovalHistoryTool(),
    FetchApprovalTool(),
    AssessProposalRiskTool(),
    FetchComplianceRequirementsTool(),
    ExtractRFPRequirementsTool(),
    SummarizeDocumentTool(),
]


class AgentOrchestrator:
    def __init__(self, db: "Session", provider: "LLMProvider") -> None:
        self._db = db
        self._provider = provider
        self._memory = get_agent_memory()

    async def run(self, contract: TaskContract) -> AgentResult:
        # 1. Input guardrails
        safe, violations = validate_task_contract(contract)
        if not safe:
            return AgentResult(
                task_id=contract.task_id,
                agent_type=contract.agent_type,
                status="failed",
                output={},
                error=f"Guardrail violations: {violations}",
            )

        # 2. Instantiate agent with all tools (agent filters by ALLOWED_TOOLS)
        try:
            agent = get_agent(
                agent_type=contract.agent_type,
                db=self._db,
                provider=self._provider,
                tools=_ALL_TOOLS,
            )
        except ValueError as exc:
            return AgentResult(
                task_id=contract.task_id,
                agent_type=contract.agent_type,
                status="failed",
                output={},
                error=str(exc),
            )

        # 3. Execute
        result = await agent.execute(contract)

        # 4. Output guardrails (warnings only)
        _, output_warnings = validate_agent_output(result.output)
        if output_warnings:
            result.audit_trail.append({"output_warnings": output_warnings})
            logger.warning("Agent %s output warnings: %s", contract.agent_type, output_warnings)

        # 5. Evaluate
        eval_result = evaluate_result(result, agent.EXPECTED_OUTPUT_FIELDS)
        result.audit_trail.append({"evaluation": eval_result})

        # 6. Record in memory
        self._memory.record(
            task_id=result.task_id,
            agent_type=result.agent_type,
            status=result.status,
            output=result.output,
            grounding_score=result.grounding_score,
            confidence=result.confidence,
            correlation_id=contract.correlation_id,
        )

        return result

    async def run_plan(self, contracts: list[TaskContract]) -> list[AgentResult]:
        results: list[AgentResult] = []
        for contract in contracts:
            result = await self.run(contract)
            results.append(result)
            # Stop plan execution on hard failure
            if result.status == "failed":
                logger.error("Plan halted at %s: %s", contract.agent_type, result.error)
                break
        return results
