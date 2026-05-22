"""
LLM prompt for proposal health narrative generation.

Uses Claude claude-haiku-4-5 (fastest/cheapest) via the Anthropic SDK.
Traces the call with Langfuse when LANGFUSE_SECRET_KEY is configured.

Returns a plain-text narrative (2–4 sentences) explaining the health score
and top improvement actions.  Returns None on any error — callers must
treat this as optional enrichment only.
"""
import json
import logging
import os
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from decision_engine.scoring.health import ProposalHealthScore

logger = logging.getLogger("decision_engine.prompts.health_analysis")

PROMPT_NAME = "proposal-health-narrative"
PROMPT_VERSION = "v1"
MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "You are an enterprise pre-sales analyst. "
    "Given a structured proposal health score, write a concise 2–4 sentence "
    "narrative for a presales manager. Cover: (1) overall readiness, "
    "(2) the most critical gap, (3) the single highest-priority action. "
    "Be direct and specific — no generic advice. Return plain text, no bullet points."
)


def _build_user_prompt(health: "ProposalHealthScore", content: dict) -> str:
    filled = [k for k in content if content.get(k)]
    missing = health.missing_requirements[:5]
    return json.dumps({
        "overall_score": health.overall_score,
        "readiness_classification": health.readiness_classification,
        "breakdown": health.breakdown.__dict__ if hasattr(health.breakdown, "__dict__") else health.breakdown,
        "risk_factors": health.risk_factors,
        "missing_requirements": missing,
        "filled_sections": filled,
    }, indent=2)


async def build_health_narrative(
    health: "ProposalHealthScore",
    content: dict,
) -> Optional[str]:
    """
    Call Claude Haiku to generate a narrative for the health score.
    Returns None if ANTHROPIC_API_KEY is absent or call fails.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)

        langfuse = _get_langfuse()
        trace = None
        if langfuse:
            trace = langfuse.trace(
                name=PROMPT_NAME,
                metadata={
                    "proposal_id": health.proposal_id,
                    "model": MODEL,
                    "prompt_version": PROMPT_VERSION,
                },
            )

        user_prompt = _build_user_prompt(health, content)

        generation_start = __import__("time").time()
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=256,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        latency_ms = int((__import__("time").time() - generation_start) * 1000)
        narrative = resp.content[0].text.strip()

        if trace:
            trace.generation(
                name="health-narrative",
                model=MODEL,
                prompt=user_prompt,
                completion=narrative,
                usage={
                    "input": resp.usage.input_tokens,
                    "output": resp.usage.output_tokens,
                },
                metadata={"latency_ms": latency_ms, "prompt_version": PROMPT_VERSION},
            )

        return narrative

    except Exception as exc:
        logger.debug("Health narrative LLM call failed: %s", exc)
        return None


def _get_langfuse():
    try:
        from telemetry.langfuse_client import get_langfuse
        return get_langfuse()
    except Exception:
        return None
