"""Anthropic Claude provider."""
import time

from copilot_engine.providers.base import LLMProvider, LLMResponse
from copilot_engine.config import CLAUDE_COPILOT_MODEL, CLAUDE_API_KEY


class ClaudeProvider(LLMProvider):
    def __init__(self):
        import anthropic
        self._client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        self._model = CLAUDE_COPILOT_MODEL

    @property
    def provider_name(self) -> str:
        return "claude"

    @property
    def model_name(self) -> str:
        return self._model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        t0 = time.monotonic()
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        latency_ms = (time.monotonic() - t0) * 1000
        return LLMResponse(
            content=msg.content[0].text,
            model=self._model,
            provider="claude",
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            latency_ms=latency_ms,
        )
