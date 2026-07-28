"""Groq Chat Completions provider (scrubbed text only — never send raw proposals)."""
import time

from copilot_engine.providers.base import LLMProvider, LLMResponse
from copilot_engine.config import GROQ_API_KEY, GROQ_COPILOT_MODEL


class GroqProvider(LLMProvider):
    def __init__(self):
        from groq import AsyncGroq

        self._client = AsyncGroq(api_key=GROQ_API_KEY)
        self._model = GROQ_COPILOT_MODEL

    @property
    def provider_name(self) -> str:
        return "groq"

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
        response = await self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        latency_ms = (time.monotonic() - t0) * 1000
        choice = response.choices[0]
        usage = response.usage
        return LLMResponse(
            content=choice.message.content or "",
            model=self._model,
            provider="groq",
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            latency_ms=latency_ms,
        )
