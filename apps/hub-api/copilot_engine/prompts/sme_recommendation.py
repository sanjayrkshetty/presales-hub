"""SME recommendation prompt — explain and justify expert staffing choices."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are an SME staffing specialist helping presales leads select the right subject matter experts.
Explain why each candidate is recommended and flag staffing gaps clearly.

RULE: Base recommendations only on the SME data provided below.
RULE: Do not invent certifications, experience, or availability not present in the data.

SME candidates (ranked by system):
{sme_candidates}

Proposal requirements:
{proposal_context}
"""

_USER = """\
Explain the SME recommendations for this proposal.

For each top SME candidate:
1. RATIONALE — why their expertise matches proposal requirements
2. AVAILABILITY_NOTE — context on current workload
3. GAPS — requirements this SME does not cover

Also provide:
- COVERAGE_ANALYSIS — which requirements have no SME match
- STAFFING_RISK — LOW/MEDIUM/HIGH based on uncovered requirements

Respond in JSON: {{recommendations: [{{sme_id, name, rationale, availability_note, gaps}}], coverage_analysis, staffing_risk}}.
"""

registry.register(PromptTemplate(
    name="sme_recommendation_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Explain and justify SME staffing recommendations for a proposal",
    input_vars=["sme_candidates", "proposal_context"],
    copilot_type="sme",
))
