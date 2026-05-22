"""Agent prompt: solution architecture recommendation."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are a solution architecture agent for presales engagements.
Recommend a high-level architecture aligned with the compliance framework and client requirements.

GROUNDING RULE: Base recommendations on the provided requirements — do not invent vendor names
or specific tooling without citing source data.
AUTHORITY: recommend — architecture must be validated by a technical SME.

Compliance requirements for the framework:
{compliance_requirements}

Institutional memory:
{memory_context}
"""

_USER = """\
Framework: {rfp_type}
Client size / context: {client_context}
Key requirements: {key_requirements}
Budget context: {deal_value_cr} Cr

Produce a JSON response with keys:
- architecture_layers (list of {{"layer": str, "components": list[str], "rationale": str}})
- integration_points (list of strings)
- phasing_suggestion (list of {{"phase": int, "scope": str, "duration_weeks": int}})
- open_questions (list of strings — items needing client clarification)
"""

registry.register(PromptTemplate(
    name="agent_solution_architecture_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Agent-level solution architecture recommendation",
    input_vars=[
        "rfp_type", "client_context", "key_requirements", "deal_value_cr",
        "compliance_requirements", "memory_context",
    ],
    copilot_type="solution",
))
