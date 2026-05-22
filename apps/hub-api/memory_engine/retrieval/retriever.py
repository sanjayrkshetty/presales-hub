"""
Memory Retriever.

Orchestrates:
  1. Embed the query text
  2. Pre-filter by memory_type and metadata
  3. Cosine similarity top-k via VectorStore
  4. Return SearchResult list

The retriever is stateless and cheap to instantiate per request.
"""
import logging
from typing import Optional

from memory_engine.embeddings.factory import get_embedding_provider
from memory_engine.storage.base import VectorStore, SearchResult
from memory_engine.config import DEFAULT_TOP_K, MAX_TOP_K

logger = logging.getLogger("memory_engine.retrieval")


class MemoryRetriever:
    def __init__(self, store: VectorStore):
        self._store = store
        self._provider = get_embedding_provider()

    def retrieve(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        memory_type: Optional[str] = None,
        metadata_filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        """
        Semantic retrieval against the vector store.

        Args:
            query: free-text search query
            top_k: number of results (capped at MAX_TOP_K)
            memory_type: filter to specific memory domain
            metadata_filter: exact-match filters on chunk metadata keys

        Returns:
            Ranked list of SearchResult (highest cosine similarity first)
        """
        k = min(top_k, MAX_TOP_K)
        query_emb = self._provider.embed(query)
        results = self._store.search(
            query_embedding=query_emb,
            top_k=k,
            memory_type=memory_type,
            metadata_filter=metadata_filter,
        )
        logger.debug(
            "Retrieved %d results for query '%s...' (type=%s)",
            len(results), query[:40], memory_type,
        )
        return results

    def retrieve_similar_to_chunk(
        self,
        chunk_id: str,
        top_k: int = DEFAULT_TOP_K,
        memory_type: Optional[str] = None,
    ) -> list[SearchResult]:
        """Find chunks similar to an existing chunk (by its stored embedding)."""
        from models.memory import MemoryChunk
        from sqlalchemy import select

        # This is called from routes that have their own DB session;
        # retrieve the embedding directly from the store.
        source_results = self._store.get_by_source(chunk_id)
        if not source_results:
            return []
        # Use first result's content as query proxy (chunk_id IS the source)
        proxy_emb = self._provider.embed(source_results[0].content)
        results = self._store.search(
            query_embedding=proxy_emb,
            top_k=top_k + 1,  # +1 to account for self
            memory_type=memory_type,
        )
        # Exclude exact self-match
        return [r for r in results if r.chunk_id != chunk_id][:top_k]
