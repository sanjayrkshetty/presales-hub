"""Select LLM provider by environment configuration."""
import copilot_engine.config as _cfg
from copilot_engine.providers.base import LLMProvider


def get_llm_provider() -> LLMProvider:
    """
    Returns the configured LLM provider.

    v1 priority: explicit LLM_PROVIDER → Groq (if key) → Claude → OpenAI → mock.
    Chat/Generate uses scrubbed text only when calling cloud providers.
    """
    if _cfg.LLM_PROVIDER == "mock":
        from copilot_engine.providers.mock_provider import MockLLMProvider
        return MockLLMProvider()

    if _cfg.LLM_PROVIDER == "groq" and _cfg.GROQ_API_KEY:
        from copilot_engine.providers.groq_provider import GroqProvider
        return GroqProvider()

    if _cfg.LLM_PROVIDER == "openai" and _cfg.OPENAI_API_KEY:
        from copilot_engine.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()

    if _cfg.LLM_PROVIDER == "claude" and _cfg.CLAUDE_API_KEY:
        from copilot_engine.providers.claude_provider import ClaudeProvider
        return ClaudeProvider()

    # Auto-detect by available keys (prefer Groq for v1)
    if _cfg.GROQ_API_KEY:
        from copilot_engine.providers.groq_provider import GroqProvider
        return GroqProvider()
    if _cfg.CLAUDE_API_KEY:
        from copilot_engine.providers.claude_provider import ClaudeProvider
        return ClaudeProvider()
    if _cfg.OPENAI_API_KEY:
        from copilot_engine.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()

    from copilot_engine.providers.mock_provider import MockLLMProvider
    return MockLLMProvider(
        '{"result": "Copilot not configured — set GROQ_API_KEY (preferred) or ANTHROPIC_API_KEY.", "status": "unconfigured"}'
    )
