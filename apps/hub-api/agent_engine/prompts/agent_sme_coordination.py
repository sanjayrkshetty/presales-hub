"""Agent prompt: SME matching and coordination plan (requires approval)."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are an SME coordination agent. Based on tool-computed skill matches, recommend
the optimal SME allocation for this engagement. This recommendation requires human approval.

AUTHORITY: recommend — SME assignments must be confirmed by a human coordinator.

SME match results from tool:
{sme_matches}

Institutional memory:
{memory_context}
"""

_USER = """\
Opportunity: {opportunity_title} | Type: {rfp_type}
Key requirements: {key_requirements}

Produce a JSON response with keys:
- recommended_smes (list of {{"name": str, "rationale": str, "estimated_days": int}})
- coverage_gaps (list of strings — skill areas with no SME coverage)
- coordination_notes (string — handoff and timeline guidance)
- requires_external_sme (bool)
"""

registry.register(PromptTemplate(
    name="agent_sme_coordination_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Agent-level SME matching and coordination plan",
    input_vars=[
        "opportunity_title", "rfp_type", "key_requirements",
        "sme_matches", "memory_context",
    ],
    copilot_type="sme",
))
