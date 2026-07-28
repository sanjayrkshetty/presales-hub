"""
Local sentence-transformers embedding provider.

Model: all-MiniLM-L6-v2 (384-dim), CPU-friendly for ~12GB RAM laptops.
Factory falls back to LocalHashEmbeddingProvider when sentence_transformers is absent.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from memory_engine.embeddings.base import EmbeddingProvider
from memory_engine.config import MINILM_MODEL, MINILM_DIMS

logger = logging.getLogger("memory_engine.embeddings.minilm")


@lru_cache(maxsize=1)
def _load_model():
    from sentence_transformers import SentenceTransformer

    logger.info("Loading embedding model %s", MINILM_MODEL)
    return SentenceTransformer(MINILM_MODEL)


class MiniLMEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        self._model = _load_model()

    @property
    def model_name(self) -> str:
        return MINILM_MODEL

    @property
    def dims(self) -> int:
        return MINILM_DIMS

    def embed(self, text: str) -> list[float]:
        vec = self._model.encode(text or "", normalize_embeddings=True)
        return vec.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]
