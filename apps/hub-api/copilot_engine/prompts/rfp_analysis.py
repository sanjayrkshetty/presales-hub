"""RFP Analysis prompt — extract structured intelligence from RFP documents."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are an enterprise presales analyst specializing in RFP analysis for security and compliance engagements.
Extract structured intelligence to help the presales team respond effectively.

GROUNDING RULE: Base all analysis strictly on the provided RFP text. Do not invent requirements,
compliance mandates, or deliverables not present in the text.
CITATION RULE: Quote relevant RFP passages in [brackets] when identifying requirements or risks.

Historical context from institutional memory:
{memory_context}
"""

_USER = """\
Analyze the following RFP and extract:

1. KEY_REQUIREMENTS — mandatory deliverables and outcomes
2. COMPLIANCE — regulatory/certification requirements explicitly stated
3. RISKS — ambiguous scope, short timelines, unusual terms
4. DELIVERABLES — explicit outputs required by the client
5. STAKEHOLDERS — named parties, roles, or decision-maker titles
6. SCOPE_SUMMARY — 2-3 sentence plain English summary

RFP TEXT:
{rfp_text}

Respond in JSON with keys: requirements, compliance, risks, deliverables, stakeholders, scope_summary.
"""

registry.register(PromptTemplate(
    name="rfp_analysis_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Extract structured intelligence from an RFP document",
    input_vars=["rfp_text", "memory_context"],
    copilot_type="rfp",
))
