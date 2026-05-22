"""Central configuration for the copilot engine."""
import os

# ── LLM Provider ──────────────────────────────────────────────────────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude")   # claude | openai | mock
CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

CLAUDE_COPILOT_MODEL = os.getenv("CLAUDE_COPILOT_MODEL", "claude-haiku-4-5-20251001")
OPENAI_COPILOT_MODEL = os.getenv("OPENAI_COPILOT_MODEL", "gpt-4o-mini")

# ── Request limits ────────────────────────────────────────────────────────────
MAX_CONTEXT_CHUNKS = 8      # max retrieved memory chunks per copilot call
MAX_RESPONSE_TOKENS = 1500
MAX_QUERY_LENGTH = 2000     # hard cap on user query length before truncation

# ── Safety ────────────────────────────────────────────────────────────────────
CITATION_REQUIRED = False   # if True, responses without citations are flagged
MIN_GROUNDING_SCORE = 0.0   # 0 = log only; raise to enforce minimum grounding
