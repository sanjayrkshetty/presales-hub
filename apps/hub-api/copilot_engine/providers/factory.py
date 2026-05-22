"""Select LLM provider by environment configuration."""
import copilot_engine.config as _cfg
from copilot_engine.providers.base import LLMProvider


def get_llm_provider() -> LLMProvider:
    """
    Returns the configured LLM provider.
    Priority: explicit LLM_PROVIDER env → ANTHROPIC_API_KEY → OPENAI_API_KEY → mock.
    Reads config at call time so test patches to cfg.* take effect.
    """
    if _cfg.LLM_PROVIDER == "openai" and _cfg.OPENAI_API_KEY:
        from copilot_engine.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()
    if _cfg.LLM_PROVIDER == "mock":
        from copilot_engine.providers.mock_provider import MockLLMProvider
        return MockLLMProvider()
    if _cfg.CLAUDE_API_KEY:
        from copilot_engine.providers.claude_provider import ClaudeProvider
        return ClaudeProvider()
    if _cfg.OPENAI_API_KEY:
        from copilot_engine.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()
    # No API key configured — fall back to mock with informative message
    from copilot_engine.providers.mock_provider import MockLLMProvider
    return MockLLMProvider(
        '{"result": "Copilot not configured — set ANTHROPIC_API_KEY or OPENAI_API_KEY.", "status": "unconfigured"}'
    )
