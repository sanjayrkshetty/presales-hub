"""
OpenAI embedding provider.

Uses text-embedding-3-small (1536 dims).  Requires OPENAI_API_KEY.
Falls back gracefully: if the API is unavailable, callers receive an error
and should catch it to fall back to the LocalHashEmbeddingProvider.

Async batch embed uses the openai AsyncOpenAI client for throughput.
"""
import logging
import os
from typing import Optional

from memory_engine.embeddings.base import EmbeddingProvider
from memory_engine.config import OPENAI_EMBEDDING_MODEL, OPENAI_EMBEDDING_DIMS

logger = logging.getLogger("memory_engine.embeddings.openai")


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    Wraps OpenAI's embedding endpoint.
    Instantiation is cheap; the HTTP client is created lazily.
    """

    def __init__(self, model: str = OPENAI_EMBEDDING_MODEL, api_key: Optional[str] = None):
        self._model = model
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client = None

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dims(self) -> int:
        return OPENAI_EMBEDDING_DIMS

    def _get_client(self):
        if self._client is None:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self._api_key)
            except ImportError as exc:
                raise RuntimeError("openai package not installed") from exc
        return self._client

    def embed(self, text: str) -> list[float]:
        client = self._get_client()
        resp = client.embeddings.create(input=text, model=self._model)
        return resp.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()
        resp = client.embeddings.create(input=texts, model=self._model)
        # OpenAI returns items in order of input index
        return [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
