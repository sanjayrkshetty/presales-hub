"""Agent prompt: executive briefing generation."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are an executive briefing agent. Produce concise, decision-ready intelligence
for leadership. Avoid operational detail — focus on deal status, risk, and action.

GROUNDING RULE: Summarise only information present in the proposal and opportunity data.
AUTHORITY: recommend — briefing text requires human review before distribution.

Workflow state:
{workflow_state}

Institutional memory:
{memory_context}
"""

_USER = """\
Opportunity: {opportunity_title} | Stage: {proposal_stage} | Deal: {deal_value_cr} Cr
Risk level: {risk_level}
Pending approvals: {pending_approvals}

Produce a JSON response with keys:
- headline (string — one sentence deal status)
- deal_snapshot ({{"value_cr": str, "stage": str, "client": str}})
- key_risks (list of strings, max 3)
- decisions_needed (list of strings)
- recommended_next_step (string)
"""

registry.register(PromptTemplate(
    name="agent_executive_briefing_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Agent-level executive briefing with workflow state context",
    input_vars=[
        "opportunity_title", "proposal_stage", "deal_value_cr",
        "risk_level", "pending_approvals", "workflow_state", "memory_context",
    ],
    copilot_type="executive",
))
