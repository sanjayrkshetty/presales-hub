"""EmbeddingProvider abstract base class."""
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """
    Contract for all embedding providers.
    Implementations must be stateless and thread-safe.
    """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier written to MemoryChunk.embedding_model for lineage."""

    @property
    @abstractmethod
    def dims(self) -> int:
        """Dimensionality of vectors produced by this provider."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """
        Embed a single text string.
        Returns a unit-normalized vector of length self.dims.
        """

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts. Default implementation calls embed() in a loop."""
        return [self.embed(t) for t in texts]
