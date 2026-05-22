"""
Embedding provider factory.

Selection order:
  1. OPENAI_API_KEY is set → OpenAIEmbeddingProvider (semantic quality)
  2. Fallback              → LocalHashEmbeddingProvider (deterministic, zero-cost)

The factory returns a singleton per process — providers are stateless and
safe to share across threads.
"""
import os
from functools import lru_cache

from memory_engine.embeddings.base import EmbeddingProvider


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    if os.getenv("OPENAI_API_KEY"):
        from memory_engine.embeddings.openai_provider import OpenAIEmbeddingProvider
        return OpenAIEmbeddingProvider()
    from memory_engine.embeddings.local_provider import LocalHashEmbeddingProvider
    return LocalHashEmbeddingProvider()
