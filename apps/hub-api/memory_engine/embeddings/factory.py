"""
Embedding provider factory.

Selection order (v1 locked):
  1. EMBEDDING_PROVIDER=hash          → LocalHashEmbeddingProvider
  2. EMBEDDING_PROVIDER=openai + key  → OpenAIEmbeddingProvider
  3. EMBEDDING_PROVIDER=minilm|auto   → MiniLM if sentence_transformers importable
  4. Fallback                         → LocalHashEmbeddingProvider

Default semantic path is local MiniLM (not Ollama, not OpenAI).
"""
import logging
import os
from functools import lru_cache

from memory_engine.embeddings.base import EmbeddingProvider
from memory_engine import config as _cfg

logger = logging.getLogger("memory_engine.embeddings.factory")


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    mode = (_cfg.EMBEDDING_PROVIDER or "auto").lower()

    if mode == "hash":
        from memory_engine.embeddings.local_provider import LocalHashEmbeddingProvider
        return LocalHashEmbeddingProvider()

    if mode == "openai" and os.getenv("OPENAI_API_KEY"):
        from memory_engine.embeddings.openai_provider import OpenAIEmbeddingProvider
        return OpenAIEmbeddingProvider()

    if mode in ("auto", "minilm"):
        try:
            from memory_engine.embeddings.minilm_provider import MiniLMEmbeddingProvider
            return MiniLMEmbeddingProvider()
        except Exception as exc:
            logger.warning("MiniLM unavailable (%s); using local hash embeddings", exc)

    from memory_engine.embeddings.local_provider import LocalHashEmbeddingProvider
    return LocalHashEmbeddingProvider()
