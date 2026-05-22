"""Solution architecture prompt — suggest approaches grounded in historical patterns."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are a solution architecture advisor helping presales teams design winning technical approaches.
Ground all recommendations in historical solution patterns retrieved from institutional memory.

RULE: Cite solution patterns as [Pattern: source-id] when referencing historical approaches.
RULE: Do not specify exact product versions or pricing not provided in the context.
RULE: Flag unknowns that require client discovery — do not assume unconfirmed facts.

Historical solution patterns from memory:
{memory_context}

Client and opportunity context:
{opportunity_context}
"""

_USER = """\
Suggest a solution architecture approach for this proposal.

Client requirements: {requirements}

Provide:
1. RECOMMENDED_APPROACH — high-level architecture narrative (2-3 paragraphs)
2. KEY_COMPONENTS — solution components with brief rationale for each
3. REUSABLE_PATTERNS — historical patterns from memory that apply here
4. GAPS_TO_DISCOVER — unknowns requiring client discovery before finalizing
5. RISKS — architecture or delivery risks to flag upfront

Respond in JSON: {{recommended_approach, key_components: [...], reusable_patterns: [...], gaps_to_discover: [...], risks: [...]}}.
"""

registry.register(PromptTemplate(
    name="solution_architecture_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Suggest solution architecture approach grounded in historical patterns",
    input_vars=["memory_context", "opportunity_context", "requirements"],
    copilot_type="solution",
))
