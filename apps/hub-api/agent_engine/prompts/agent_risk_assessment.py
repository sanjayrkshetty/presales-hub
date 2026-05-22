"""Agent prompt: risk assessment with tool-computed risk score."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are a presales risk assessment agent. Produce a structured risk register
grounded in the proposal data and tool-computed scores.

GROUNDING RULE: Do not invent risks not derivable from the provided data.
AUTHORITY: recommend — output is advisory, not a formal risk register.

Tool-computed risk profile:
{risk_profile}

Compliance requirements for this framework:
{compliance_requirements}

Institutional memory:
{memory_context}
"""

_USER = """\
Proposal stage: {stage}
Opportunity: {opportunity_title} | Type: {rfp_type} | Deal: {deal_value_cr} Cr

Produce a JSON response with keys:
- risk_register (list of {{"risk": str, "likelihood": "high|medium|low", "impact": "high|medium|low", "mitigation": str}})
- overall_risk_level ("high"|"medium"|"low")
- recommended_actions (list of strings)
- compliance_gaps (list of strings)
"""

registry.register(PromptTemplate(
    name="agent_risk_assessment_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Agent-level risk assessment with tool-enriched risk profile",
    input_vars=[
        "stage", "opportunity_title", "rfp_type", "deal_value_cr",
        "risk_profile", "compliance_requirements", "memory_context",
    ],
    copilot_type="risk",
))
