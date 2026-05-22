"""Agent prompt: project timeline planning (requires approval)."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are a timeline planning agent. Generate a realistic delivery timeline for this engagement.
This plan requires human approval before being shared with the client.

GROUNDING RULE: Base duration estimates on framework complexity and deal size, not assumptions.
AUTHORITY: draft — timeline requires human approval before client communication.

Workflow state:
{workflow_state}

Institutional memory (past similar timelines):
{memory_context}
"""

_USER = """\
Framework: {rfp_type}
Deal value: {deal_value_cr} Cr
Proposal stage: {proposal_stage}
SME availability notes: {sme_notes}

Produce a JSON response with keys:
- milestones (list of {{"name": str, "week": int, "owner": str, "dependencies": list[str]}})
- total_weeks (int)
- critical_path (list of strings)
- risk_buffers (list of {{"milestone": str, "buffer_weeks": int, "reason": str}})
- assumptions (list of strings)
"""

registry.register(PromptTemplate(
    name="agent_timeline_planning_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Agent-level timeline planning with approval gate",
    input_vars=[
        "rfp_type", "deal_value_cr", "proposal_stage",
        "sme_notes", "workflow_state", "memory_context",
    ],
    copilot_type="workflow",
))
