"""Simulation harness — runs agents against synthetic contracts without DB or LLM."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from agent_engine.execution.task_contract import AgentResult, TaskContract
from agent_engine.evaluators.agent_evaluator import evaluate_result


@dataclass
class SimulationScenario:
    name: str
    agent_type: str
    input_data: dict
    proposal_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    expected_status: str = "completed"
    expected_fields: list[str] | None = None


@dataclass
class SimulationResult:
    scenario_name: str
    agent_type: str
    status: str
    passed: bool
    eval_score: float
    errors: list[str]
    latency_ms: float


async def run_simulation(
    scenario: SimulationScenario,
    db,
    provider,
) -> SimulationResult:
    from agent_engine.agents.registry import get_agent
    from agent_engine.tools.proposal_tools import FetchProposalTool, ListProposalSectionsTool
    from agent_engine.tools.document_tools import ExtractRFPRequirementsTool, SummarizeDocumentTool

    contract = TaskContract(
        agent_type=scenario.agent_type,
        proposal_id=scenario.proposal_id,
        opportunity_id=scenario.opportunity_id,
        input_data=scenario.input_data,
    )

    # Minimal tool set for simulation (no DB writes, no external calls)
    tools = [
        FetchProposalTool(),
        ListProposalSectionsTool(),
        ExtractRFPRequirementsTool(),
        SummarizeDocumentTool(),
    ]

    agent = get_agent(agent_type=scenario.agent_type, db=db, provider=provider, tools=tools)
    result = await agent.execute(contract)
    eval_result = evaluate_result(result, scenario.expected_fields)
    passed = result.status == scenario.expected_status

    return SimulationResult(
        scenario_name=scenario.name,
        agent_type=scenario.agent_type,
        status=result.status,
        passed=passed,
        eval_score=eval_result["overall_score"],
        errors=[result.error] if result.error else [],
        latency_ms=result.latency_ms,
    )


async def run_simulation_suite(
    scenarios: list[SimulationScenario],
    db,
    provider,
) -> list[SimulationResult]:
    tasks = [run_simulation(s, db, provider) for s in scenarios]
    return list(await asyncio.gather(*tasks))
