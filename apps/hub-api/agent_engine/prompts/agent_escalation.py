"""Agent prompt: escalation reasoning — surfaces issues requiring leadership action."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are an escalation agent. Your role is to identify situations requiring senior leadership
attention and draft a clear escalation briefing. Escalation outputs require human approval.

GROUNDING RULE: Only escalate issues supported by observable evidence in the data.
AUTHORITY: draft — escalation requires human approval before being acted on.

Risk profile:
{risk_profile}

Approval history:
{approval_history}

Institutional memory:
{memory_context}
"""

_USER = """\
Proposal stage: {proposal_stage}
Opportunity: {opportunity_title} | Deal: {deal_value_cr} Cr
Pending approvals: {pending_approvals}
Trigger reason: {trigger_reason}

Produce a JSON response with keys:
- escalation_required (bool)
- severity ("critical"|"high"|"medium")
- issue_summary (string)
- evidence (list of strings)
- recommended_escalation_path (string — who should be looped in)
- suggested_actions (list of strings)
"""

registry.register(PromptTemplate(
    name="agent_escalation_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Agent-level escalation briefing with approval gate",
    input_vars=[
        "proposal_stage", "opportunity_title", "deal_value_cr",
        "pending_approvals", "trigger_reason", "risk_profile",
        "approval_history", "memory_context",
    ],
    copilot_type="workflow",
))
