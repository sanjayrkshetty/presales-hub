"""OpenAI ChatCompletion provider."""
import time

from copilot_engine.providers.base import LLMProvider, LLMResponse
from copilot_engine.config import OPENAI_COPILOT_MODEL, OPENAI_API_KEY


class OpenAIProvider(LLMProvider):
    def __init__(self):
        import openai
        self._client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        self._model = OPENAI_COPILOT_MODEL

    @property
    def provider_name(self) -> str:
        return "openai"

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
        return LLMResponse(
            content=choice.message.content or "",
            model=self._model,
            provider="openai",
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            latency_ms=latency_ms,
        )
