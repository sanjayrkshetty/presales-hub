from __future__ import annotations

from typing import TYPE_CHECKING, Type

from agent_engine.agents.base import AgentBase
from agent_engine.agents.rfp_analysis_agent import RFPAnalysisAgent
from agent_engine.agents.proposal_drafting_agent import ProposalDraftingAgent
from agent_engine.agents.risk_assessment_agent import RiskAssessmentAgent
from agent_engine.agents.compliance_check_agent import ComplianceCheckAgent
from agent_engine.agents.sme_coordination_agent import SMECoordinationAgent
from agent_engine.agents.executive_briefing_agent import ExecutiveBriefingAgent
from agent_engine.agents.approval_reasoning_agent import ApprovalReasoningAgent
from agent_engine.agents.solution_architecture_agent import SolutionArchitectureAgent
from agent_engine.agents.timeline_planning_agent import TimelinePlanningAgent
from agent_engine.agents.escalation_agent import EscalationAgent

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from copilot_engine.providers.base import LLMProvider
    from agent_engine.tools.base import AgentTool

_REGISTRY: dict[str, Type[AgentBase]] = {
    "rfp_analysis": RFPAnalysisAgent,
    "proposal_drafting": ProposalDraftingAgent,
    "risk_assessment": RiskAssessmentAgent,
    "compliance_check": ComplianceCheckAgent,
    "sme_coordination": SMECoordinationAgent,
    "executive_briefing": ExecutiveBriefingAgent,
    "approval_reasoning": ApprovalReasoningAgent,
    "solution_architecture": SolutionArchitectureAgent,
    "timeline_planning": TimelinePlanningAgent,
    "escalation": EscalationAgent,
}


def get_agent(
    agent_type: str,
    db: "Session",
    provider: "LLMProvider",
    tools: list["AgentTool"] | None = None,
) -> AgentBase:
    cls = _REGISTRY.get(agent_type)
    if cls is None:
        raise ValueError(f"Unknown agent type: {agent_type!r}. Available: {list(_REGISTRY)}")
    return cls(db=db, provider=provider, tools=tools or [])


def list_agent_types() -> list[dict]:
    return [
        {
            "agent_type": cls.AGENT_TYPE,
            "authority_level": cls.AUTHORITY_LEVEL,
            "allowed_tools": cls.ALLOWED_TOOLS,
            "prompt_name": cls.PROMPT_NAME,
        }
        for cls in _REGISTRY.values()
    ]
