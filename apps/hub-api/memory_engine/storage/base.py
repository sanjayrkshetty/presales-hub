"""VectorStore abstract base class."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchResult:
    chunk_id: str
    source_id: str
    source_type: str
    memory_type: str
    section: Optional[str]
    content: str
    score: float
    metadata: dict = field(default_factory=dict)
    embedding_model: str = ""

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "memory_type": self.memory_type,
            "section": self.section,
            "content": self.content,
            "score": round(self.score, 4),
            "metadata": self.metadata,
            "embedding_model": self.embedding_model,
        }


class VectorStore(ABC):
    """
    Storage + similarity search contract.

    Implementations handle persistence; callers provide embeddings.
    All methods are synchronous (wraps DB session).
    """

    @abstractmethod
    def upsert(
        self,
        chunk_id: str,
        memory_type: str,
        source_type: str,
        source_id: str,
        section: Optional[str],
        content: str,
        embedding: list[float],
        model_name: str,
        metadata: dict,
        source_version: int = 1,
    ) -> None:
        """Insert or update a chunk. Keyed on chunk_id."""

    @abstractmethod
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        memory_type: Optional[str] = None,
        metadata_filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        """
        Return top_k chunks by cosine similarity.
        Optional pre-filtering by memory_type and metadata key-value pairs.
        """

    @abstractmethod
    def deactivate_source(self, source_id: str) -> int:
        """Soft-delete all active chunks for source_id. Returns count affected."""

    @abstractmethod
    def count(self, memory_type: Optional[str] = None) -> int:
        """Count active chunks, optionally filtered by memory_type."""

    @abstractmethod
    def get_by_source(self, source_id: str) -> list[SearchResult]:
        """Retrieve all active chunks for a given source."""
