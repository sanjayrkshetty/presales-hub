from __future__ import annotations

import uuid
from agent_engine.execution.task_contract import TaskContract
from agent_engine.config import APPROVAL_REQUIRED_AGENTS


_PLAN_TEMPLATES: dict[str, list[str]] = {
    "rfp_to_proposal": [
        "rfp_analysis",
        "compliance_check",
        "risk_assessment",
        "sme_coordination",
        "solution_architecture",
        "proposal_drafting",
        "timeline_planning",
    ],
    "proposal_review": [
        "compliance_check",
        "risk_assessment",
        "approval_reasoning",
    ],
    "executive_update": [
        "risk_assessment",
        "executive_briefing",
    ],
    "escalation_review": [
        "risk_assessment",
        "approval_reasoning",
        "escalation",
    ],
}


def build_plan(
    plan_name: str,
    proposal_id: str | None,
    opportunity_id: str | None,
    base_input: dict,
) -> list[TaskContract]:
    agent_sequence = _PLAN_TEMPLATES.get(plan_name)
    if agent_sequence is None:
        raise ValueError(f"Unknown plan: {plan_name!r}. Available: {list(_PLAN_TEMPLATES)}")

    correlation_id = str(uuid.uuid4())
    contracts: list[TaskContract] = []

    for agent_type in agent_sequence:
        contracts.append(
            TaskContract(
                agent_type=agent_type,
                proposal_id=proposal_id,
                opportunity_id=opportunity_id,
                input_data=dict(base_input),
                requires_approval=agent_type in APPROVAL_REQUIRED_AGENTS,
                correlation_id=correlation_id,
            )
        )

    return contracts


def list_plans() -> list[dict]:
    return [
        {"plan_name": name, "steps": steps}
        for name, steps in _PLAN_TEMPLATES.items()
    ]
