"""Central configuration for the copilot engine."""
import os

# ── LLM Provider ──────────────────────────────────────────────────────────────
# v1 Generate/chat: Groq on scrubbed text only (not Ollama). mock for CI.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")   # groq | claude | openai | mock
CLAUDE_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

CLAUDE_COPILOT_MODEL = os.getenv("CLAUDE_COPILOT_MODEL", "claude-haiku-4-5-20251001")
OPENAI_COPILOT_MODEL = os.getenv("OPENAI_COPILOT_MODEL", "gpt-4o-mini")
GROQ_COPILOT_MODEL = os.getenv("GROQ_COPILOT_MODEL", "llama-3.1-8b-instant")

# ── Request limits ────────────────────────────────────────────────────────────
MAX_CONTEXT_CHUNKS = 8      # max retrieved memory chunks per copilot call
MAX_RESPONSE_TOKENS = 1500
MAX_QUERY_LENGTH = 2000     # hard cap on user query length before truncation

# ── Safety ────────────────────────────────────────────────────────────────────
CITATION_REQUIRED = False   # if True, responses without citations are flagged
MIN_GROUNDING_SCORE = 0.0   # 0 = log only; raise to enforce minimum grounding
