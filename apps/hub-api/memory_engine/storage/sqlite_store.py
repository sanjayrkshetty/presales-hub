"""
SQLite-compatible vector store.

Persists chunks in the memory_chunks table (SQLAlchemy ORM).
Cosine similarity is computed application-side in pure Python.

This store is the universal fallback — it works with any SQL backend.
For PostgreSQL at scale, replace with PgVectorStore (HNSW index).

Performance characteristics:
  - Upsert: O(1) — single SQL row
  - Search: O(N * D) where N = active chunks, D = embedding dims
  - Suitable for up to ~50k chunks at D=128 (local hash)
  - At D=1536 (OpenAI), comfortable to ~10k chunks before latency degrades
"""
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from models.memory import MemoryChunk, make_chunk_id
from memory_engine.storage.base import VectorStore, SearchResult

logger = logging.getLogger("memory_engine.storage.sqlite")


def _cosine(a: list[float], b: list[float]) -> float:
    """Dot product of two unit-normalized vectors (= cosine similarity)."""
    return sum(x * y for x, y in zip(a, b))


class SqliteVectorStore(VectorStore):
    """Application-side cosine similarity over SQL-stored JSON embeddings."""

    def __init__(self, db: Session):
        self._db = db

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
        existing = self._db.scalar(
            select(MemoryChunk).where(MemoryChunk.chunk_id == chunk_id)
        )
        if existing:
            existing.embedding_json = json.dumps(embedding)
            existing.embedding_model = model_name
            existing.embedding_dims = len(embedding)
            existing.metadata_json = json.dumps(metadata)
            existing.source_version = source_version
            existing.indexed_at = datetime.utcnow()
            existing.is_active = True
        else:
            chunk = MemoryChunk(
                chunk_id=chunk_id,
                memory_type=memory_type,
                source_type=source_type,
                source_id=source_id,
                source_version=source_version,
                section=section,
                content=content,
                is_active=True,
            )
            chunk.set_embedding(embedding, model_name)
            chunk.set_metadata(metadata)
            self._db.add(chunk)
        self._db.commit()

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        memory_type: Optional[str] = None,
        metadata_filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        q = select(MemoryChunk).where(MemoryChunk.is_active == True)  # noqa: E712
        if memory_type:
            q = q.where(MemoryChunk.memory_type == memory_type)
        rows = self._db.scalars(q).all()

        scored: list[tuple[float, MemoryChunk]] = []
        for chunk in rows:
            emb = chunk.get_embedding()
            if not emb or len(emb) != len(query_embedding):
                continue
            # Metadata pre-filter
            if metadata_filter:
                meta = chunk.get_metadata()
                if not all(meta.get(k) == v for k, v in metadata_filter.items()):
                    continue
            score = _cosine(query_embedding, emb)
            scored.append((score, chunk))

        scored.sort(key=lambda t: t[0], reverse=True)
        return [
            SearchResult(
                chunk_id=c.chunk_id,
                source_id=c.source_id,
                source_type=c.source_type,
                memory_type=c.memory_type,
                section=c.section,
                content=c.content,
                score=s,
                metadata=c.get_metadata(),
                embedding_model=c.embedding_model,
            )
            for s, c in scored[:top_k]
        ]

    def deactivate_source(self, source_id: str) -> int:
        rows = self._db.scalars(
            select(MemoryChunk).where(
                and_(MemoryChunk.source_id == source_id, MemoryChunk.is_active == True)  # noqa: E712
            )
        ).all()
        for r in rows:
            r.is_active = False
        self._db.commit()
        return len(rows)

    def count(self, memory_type: Optional[str] = None) -> int:
        q = select(MemoryChunk).where(MemoryChunk.is_active == True)  # noqa: E712
        if memory_type:
            q = q.where(MemoryChunk.memory_type == memory_type)
        return len(self._db.scalars(q).all())

    def get_by_source(self, source_id: str) -> list[SearchResult]:
        rows = self._db.scalars(
            select(MemoryChunk).where(
                and_(MemoryChunk.source_id == source_id, MemoryChunk.is_active == True)  # noqa: E712
            )
        ).all()
        return [
            SearchResult(
                chunk_id=r.chunk_id,
                source_id=r.source_id,
                source_type=r.source_type,
                memory_type=r.memory_type,
                section=r.section,
                content=r.content,
                score=1.0,
                metadata=r.get_metadata(),
                embedding_model=r.embedding_model,
            )
            for r in rows
        ]
