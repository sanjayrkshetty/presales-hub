"""
MemoryIndexer — orchestrates the full ingestion pipeline.

Pipeline:
  RawChunk list
    → EmbeddingProvider.embed()    (compute vectors)
    → VectorStore.upsert()         (persist with dedup via chunk_id)

Deduplication: SqliteVectorStore.upsert() is idempotent on chunk_id.
Re-indexing pattern:
  1. Call deactivate_source(source_id) — soft-deletes stale chunks
  2. Call index_chunks() — inserts fresh chunks
  This preserves query continuity during index updates.

Telemetry: emits a trace_span per indexing batch.
"""
import logging
from typing import Optional

from memory_engine.chunking.splitter import RawChunk
from memory_engine.embeddings.base import EmbeddingProvider
from memory_engine.embeddings.factory import get_embedding_provider
from memory_engine.storage.base import VectorStore
from telemetry.tracing import trace_span

logger = logging.getLogger("memory_engine.indexing")


class MemoryIndexer:
    """
    Stateless indexer — one instance per request is fine.
    Accepts any EmbeddingProvider + VectorStore (injected for testability).
    """

    def __init__(
        self,
        store: VectorStore,
        provider: Optional[EmbeddingProvider] = None,
    ):
        self._store = store
        self._provider = provider or get_embedding_provider()

    def index_chunks(self, chunks: list[RawChunk]) -> int:
        """
        Embed and upsert a list of RawChunks.
        Returns count of chunks successfully indexed.
        """
        if not chunks:
            return 0

        with trace_span("memory.index_chunks", metadata={"count": len(chunks)}):
            texts = [c.content for c in chunks]
            try:
                embeddings = self._provider.embed_batch(texts)
            except Exception as exc:
                logger.error("Embedding batch failed: %s", exc)
                return 0

            indexed = 0
            for chunk, emb in zip(chunks, embeddings):
                try:
                    self._store.upsert(
                        chunk_id=chunk.chunk_id,
                        memory_type=chunk.memory_type,
                        source_type=chunk.source_type,
                        source_id=chunk.source_id,
                        section=chunk.section,
                        content=chunk.content,
                        embedding=emb,
                        model_name=self._provider.model_name,
                        metadata=chunk.metadata,
                        source_version=chunk.source_version,
                    )
                    indexed += 1
                except Exception as exc:
                    logger.warning("Upsert failed for chunk %s: %s", chunk.chunk_id, exc)

            logger.info(
                "Indexed %d/%d chunks",
                indexed, len(chunks),
                extra={"indexed": indexed, "total": len(chunks)},
            )
            return indexed

    def reindex_source(self, source_id: str, chunks: list[RawChunk]) -> dict:
        """
        Safely re-index a source:
        1. Deactivate stale chunks
        2. Index new chunks
        """
        deactivated = self._store.deactivate_source(source_id)
        indexed = self.index_chunks(chunks)
        return {
            "source_id": source_id,
            "deactivated": deactivated,
            "indexed": indexed,
        }
