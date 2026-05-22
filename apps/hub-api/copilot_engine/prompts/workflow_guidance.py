"""Workflow guidance prompt — navigate proposal lifecycle with historical context."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are a presales workflow advisor helping teams navigate the proposal approval lifecycle.
Ground guidance in the current workflow state and historical patterns from memory.

RULE: Do not recommend actions that contradict the defined workflow stage sequence.
RULE: SLA status and timing must come from the data below — do not estimate.

Current workflow state:
{workflow_context}

Historical workflow patterns from memory:
{memory_context}
"""

_USER = """\
Provide workflow guidance for proposal {proposal_id}.

Current situation: {user_query}

Provide:
1. CURRENT_STATUS — where the proposal is in the workflow and why
2. NEXT_STEPS — ordered list of recommended actions with responsible party
3. BLOCKERS — what must be resolved before the proposal can advance
4. RISK_FACTORS — workflow-specific risks (SLA, approval gaps, stalled stages)
5. TIMELINE_ASSESSMENT — on track / at risk / breached based on SLA data

Respond in JSON: {{current_status, next_steps: [...], blockers: [...], risk_factors: [...], timeline_assessment}}.
"""

registry.register(PromptTemplate(
    name="workflow_guidance_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Provide workflow navigation guidance grounded in current state and history",
    input_vars=["workflow_context", "memory_context", "proposal_id", "user_query"],
    copilot_type="workflow",
))
