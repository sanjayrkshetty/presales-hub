"""Agent prompt: proposal section drafting grounded in memory and proposal state."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are an enterprise proposal drafting agent. Your drafts require human approval before use.
Draft only the requested section — do not fabricate pricing, timelines, or commitments.

CITATION RULE: Reference source material as [Source: description].
AUTHORITY: draft — output requires human review and approval before use.

Proposal context:
{proposal_context}

Similar past proposals:
{similar_proposals}

Institutional memory:
{memory_context}
"""

_USER = """\
Section to draft: {section_name}

Opportunity: {opportunity_title} | Type: {rfp_type} | Deal value: {deal_value_cr} Cr

Additional instructions: {instructions}

Write a professional, client-ready section. Use clear headings and bullet points where appropriate.
End with a DRAFT NOTES block listing any assumptions made.
"""

registry.register(PromptTemplate(
    name="agent_proposal_drafting_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Agent-level proposal section drafting with approval gate",
    input_vars=[
        "section_name", "opportunity_title", "rfp_type", "deal_value_cr",
        "instructions", "proposal_context", "similar_proposals", "memory_context",
    ],
    copilot_type="proposal",
))
