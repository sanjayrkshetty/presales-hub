"""
LLM prompt for deal risk narrative.

Generates a brief risk narrative for a DealRiskScore.
Same pattern as health_analysis: deterministic score first, LLM narrates.
Returns None on any error.
"""
import json
import logging
import os
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from decision_engine.scoring.deal_risk import DealRiskScore

logger = logging.getLogger("decision_engine.prompts.risk_assessment")

PROMPT_NAME = "deal-risk-narrative"
PROMPT_VERSION = "v1"
MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = (
    "You are an enterprise pre-sales risk advisor. "
    "Given a structured deal risk assessment, write 2–3 sentences for a sales director. "
    "Mention the dominant risk factor, its business implication, and the top mitigation. "
    "Be precise — no platitudes. Return plain text only."
)


async def build_risk_narrative(risk: "DealRiskScore") -> Optional[str]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)

        user_prompt = json.dumps(risk.to_dict(), indent=2)
        resp = await client.messages.create(
            model=MODEL,
            max_tokens=200,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as exc:
        logger.debug("Risk narrative LLM call failed: %s", exc)
        return None
