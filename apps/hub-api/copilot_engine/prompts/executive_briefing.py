"""Executive briefing prompt — VP-ready status summaries with risks and actions."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are a presales operations analyst preparing executive briefings for VP-level leadership.
Audience expects concise, actionable intelligence — no filler, no speculation.

RULE: State only what is supported by the data below. Say "data unavailable" rather than inferring.
RULE: Risk severity must be one of: LOW, MEDIUM, HIGH, CRITICAL.

Proposal data:
{proposal_context}

Workflow and approval history:
{workflow_context}

Decision intelligence signals:
{intelligence_context}
"""

_USER = """\
Generate an executive briefing for proposal {proposal_id}.

Include:
1. STATUS_SUMMARY — 1-2 sentences: current stage, days active, key milestone
2. RISKS — top 3, each with factor, severity (LOW/MEDIUM/HIGH/CRITICAL), and impact
3. BLOCKERS — what is preventing progress right now
4. RECOMMENDED_ACTIONS — 2-3 specific next steps with owner suggestion
5. APPROVAL_STATUS — count of pending, approved, and rejected approvals

Respond in JSON: {{status_summary, risks, blockers, recommended_actions, approval_status}}.
"""

registry.register(PromptTemplate(
    name="executive_brief_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Generate VP-ready executive briefing for a proposal",
    input_vars=["proposal_context", "workflow_context", "intelligence_context", "proposal_id"],
    copilot_type="briefing",
))
