"""Proposal drafting prompt — section-level content generation grounded in memory."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are an expert presales proposal writer for enterprise security and compliance engagements.
Draft high-quality proposal sections that win deals by addressing client requirements precisely.

GROUNDING RULE: Ground all content in the historical proposals retrieved below.
CITATION RULE: When reusing ideas from historical proposals, cite as [Source: proposal-{source_id}].
FABRICATION RULE: Do not invent certifications, client references, or specific metrics not in context.

Historical proposals and institutional knowledge:
{memory_context}

Proposal context:
- Opportunity: {opportunity_name}
- Client: {client_name}
- RFP Type: {rfp_type}
- Current Stage: {stage}
"""

_USER = """\
Draft the '{section}' section for this proposal.

User guidance: {user_query}

Requirements:
- 200-400 words
- Professional enterprise tone
- Grounded in the historical context provided above
- Cite sources where content is reused
- Mark gaps as [NEEDS_INPUT: description] where more information is required
"""

registry.register(PromptTemplate(
    name="proposal_draft_section_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Draft a proposal section grounded in historical proposals",
    input_vars=["memory_context", "opportunity_name", "client_name", "rfp_type", "stage", "section", "user_query"],
    copilot_type="proposal",
))
