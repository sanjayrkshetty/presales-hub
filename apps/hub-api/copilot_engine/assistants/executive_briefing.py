"""
Executive Briefing Copilot.

Capabilities:
  - Proposal status summary
  - Risk and blocker explanation
  - Leadership-ready briefings
  - Escalation summaries
"""
import json
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Proposal
from copilot_engine.orchestration.copilot_runner import CopilotRunner, CopilotResponse
from copilot_engine.context_builders.proposal_context import ProposalContextBuilder
from copilot_engine.providers.base import LLMProvider

import copilot_engine.prompts.executive_briefing  # noqa: F401
import copilot_engine.prompts.risk_explanation    # noqa: F401

logger = logging.getLogger("copilot_engine.assistants.executive_briefing")

_BRIEF_FIELDS = ["status_summary", "risks", "blockers", "recommended_actions", "approval_status"]
_RISK_FIELDS = ["risks", "overall_risk_level", "top_priority_action"]


class ExecutiveBriefingCopilot:
    def __init__(self, db: Session, provider: Optional[LLMProvider] = None):
        self._db = db
        self._runner = CopilotRunner(db, provider)

    async def brief(self, proposal_id: str) -> CopilotResponse:
        """Generate a VP-ready executive briefing for the proposal."""
        ctx_builder = ProposalContextBuilder(self._db)
        ctx = ctx_builder.build(proposal_id)
        proposal_text = ProposalContextBuilder.to_text(ctx)

        # Build workflow/approval context summary
        approvals = ctx.get("approvals", [])
        workflow_text = _format_workflow_context(ctx)

        # Intelligence context (health score stub — wired to decision_engine in production)
        intelligence_text = _format_intelligence_context(ctx)

        return await self._runner.run(
            prompt_name="executive_brief_v1",
            prompt_vars={
                "proposal_id": proposal_id,
                "proposal_context": proposal_text,
                "workflow_context": workflow_text,
                "intelligence_context": intelligence_text,
            },
            expected_json_fields=_BRIEF_FIELDS,
        )

    async def explain_risks(self, proposal_id: str) -> CopilotResponse:
        """Explain proposal risks in plain language."""
        ctx_builder = ProposalContextBuilder(self._db)
        ctx = ctx_builder.build(proposal_id)

        risk_data = _format_risk_data(ctx)

        return await self._runner.run(
            prompt_name="risk_explanation_v1",
            prompt_vars={
                "risk_data": risk_data,
                "memory_context": "No historical risk patterns loaded.",
            },
            expected_json_fields=_RISK_FIELDS,
        )


def _format_workflow_context(ctx: dict) -> str:
    approvals = ctx.get("approvals", [])
    if not approvals:
        return "No approvals recorded."
    lines = [f"Stage: {ctx.get('stage')} | Days active: {ctx.get('days_active')}"]
    for a in approvals:
        lines.append(f"  [{a['stage']}] {a['status']} — approver: {a.get('approver_id') or 'unassigned'}")
    return "\n".join(lines)


def _format_intelligence_context(ctx: dict) -> str:
    days = ctx.get("days_active") or 0
    approvals = ctx.get("approvals", [])
    pending = sum(1 for a in approvals if a["status"] == "pending")
    return (
        f"Days active: {days}\n"
        f"Pending approvals: {pending}\n"
        f"Stage: {ctx.get('stage')}"
    )


def _format_risk_data(ctx: dict) -> str:
    days = ctx.get("days_active") or 0
    content = ctx.get("content") or {}
    approvals = ctx.get("approvals", [])
    pending = sum(1 for a in approvals if a["status"] == "pending")
    rejected = sum(1 for a in approvals if a["status"] == "rejected")

    filled_sections = sum(1 for v in content.values() if v)
    total_sections = len(content) if content else 1

    lines = [
        f"Stage: {ctx.get('stage')} | Days active: {days}",
        f"Content completeness: {filled_sections}/{total_sections} sections filled",
        f"Approvals: {pending} pending, {rejected} rejected",
        f"Has timeline: {'Yes' if content.get('timeline') else 'No'}",
        f"Has risk matrix: {'Yes' if content.get('risk_matrix') else 'No'}",
    ]
    return "\n".join(lines)
