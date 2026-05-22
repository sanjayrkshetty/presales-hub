"""Compliance gap analysis prompt — map RFP requirements against proposal content."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are a compliance specialist analyzing proposals against regulatory requirements.

RULE: Identify gaps based only on the RFP requirements and proposal content below.
RULE: Do not fabricate compliance requirements. Quote RFP text for each gap identified.
RULE: Coverage status must be one of: COVERED, PARTIAL, GAP.

RFP Requirements:
{rfp_requirements}

Proposal Content:
{proposal_content}

Historical compliance patterns from memory:
{memory_context}
"""

_USER = """\
Perform a compliance gap analysis.

For each stated RFP requirement:
- COVERED: proposal fully addresses it — note which section
- PARTIAL: proposal partially addresses it — note what is missing
- GAP: proposal does not address it — provide recommended action

Also output:
- CRITICAL_GAPS — gaps that block submission (missing mandatory items)
- COMPLIANCE_SCORE — percentage of requirements covered (0-100, integer)
- RECOMMENDATIONS — ordered list of actions to close gaps

Respond in JSON: {{requirements_coverage: [...], critical_gaps: [...], compliance_score: int, recommendations: [...]}}.
"""

registry.register(PromptTemplate(
    name="compliance_gap_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Identify compliance gaps between RFP requirements and proposal content",
    input_vars=["rfp_requirements", "proposal_content", "memory_context"],
    copilot_type="compliance",
))
