"""
Local hash-based embedding provider.

Produces deterministic, normalized dense vectors via a bag-of-words hash
projection.  No external dependencies, no API calls, instant throughput.

Algorithm:
  1. Tokenize text (lowercase, split on whitespace + punctuation)
  2. For each token, compute MD5 → map to a bucket in [0, dims)
  3. Accumulate counts
  4. L2-normalize

Properties:
  - Deterministic: same input always → same output
  - Cosine similarity reflects vocabulary overlap (Jaccard-like)
  - Fast: O(n_tokens) time, O(dims) space
  - Suitable for dev, test, and low-traffic production

Limitations:
  - No semantic understanding (antonyms score similar to synonyms)
  - Not suitable for cross-language retrieval
  Replace with OpenAIProvider in production for semantic quality.
"""
import hashlib
import re

from memory_engine.embeddings.base import EmbeddingProvider
from memory_engine.config import LOCAL_HASH_DIMS, LOCAL_HASH_MODEL


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _l2_norm(vec: list[float]) -> list[float]:
    norm = sum(x * x for x in vec) ** 0.5
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


class LocalHashEmbeddingProvider(EmbeddingProvider):
    """Pure-Python bag-of-words hash projection. No deps beyond stdlib."""

    def __init__(self, dims: int = LOCAL_HASH_DIMS):
        self._dims = dims

    @property
    def model_name(self) -> str:
        return LOCAL_HASH_MODEL

    @property
    def dims(self) -> int:
        return self._dims

    def embed(self, text: str) -> list[float]:
        tokens = _tokenize(text)
        vec = [0.0] * self._dims
        for token in tokens:
            digest = hashlib.md5(token.encode(), usedforsecurity=False).digest()
            # Use 4 bytes → index in [0, dims)
            idx = int.from_bytes(digest[:4], "little") % self._dims
            vec[idx] += 1.0
        return _l2_norm(vec)
