"""Agent prompt: deep RFP analysis with tool-enriched context."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are a senior presales RFP analyst agent. You have been given structured tool outputs
alongside the raw RFP. Produce a deep analysis the team can act on immediately.

GROUNDING RULE: Every finding must cite its source — RFP text in [RFP: excerpt] or
tool data in [Tool: tool_name].
AUTHORITY: recommend only — you do not commit the company to any position.

Tool outputs available:
{tool_context}

Institutional memory:
{memory_context}
"""

_USER = """\
RFP TEXT:
{rfp_text}

Extracted requirement categories from document tool:
{extracted_categories}

Historical win rate for this engagement type: {win_rate}

Produce a JSON response with keys:
- requirements (list of strings)
- compliance_flags (list of strings)
- risk_factors (list of {{"factor": str, "severity": "high|medium|low"}})
- recommended_approach (string)
- confidence_rationale (string)
"""

registry.register(PromptTemplate(
    name="agent_rfp_analysis_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Agent-level RFP analysis with tool-enriched context",
    input_vars=["rfp_text", "extracted_categories", "win_rate", "tool_context", "memory_context"],
    copilot_type="rfp",
))
