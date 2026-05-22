"""Agent prompt: compliance gap analysis against known framework requirements."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are a compliance analysis agent specialising in security certification frameworks.
Map the proposal content against the framework requirements provided by the tool.

CITATION RULE: For each gap, cite the exact requirement it violates.
AUTHORITY: recommend — this is a gap analysis, not a formal audit opinion.

Framework requirements:
{framework_requirements}

Institutional memory:
{memory_context}
"""

_USER = """\
Framework: {rfp_type}
Proposal content sections: {proposal_sections}
Proposal content summary:
{content_summary}

Produce a JSON response with keys:
- covered (list of {{"requirement": str, "evidence": str}})
- gaps (list of {{"requirement": str, "gap_description": str, "severity": "critical|major|minor"}})
- coverage_score (float 0-1)
- recommended_additions (list of strings)
"""

registry.register(PromptTemplate(
    name="agent_compliance_check_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Agent-level compliance gap check against framework requirements",
    input_vars=[
        "rfp_type", "proposal_sections", "content_summary",
        "framework_requirements", "memory_context",
    ],
    copilot_type="compliance",
))
