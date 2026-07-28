"""
pgvector-backed vector store for production PostgreSQL.

Requires:
  - PostgreSQL with pgvector extension installed
  - `pip install pgvector`
  - Column altered: ALTER TABLE memory_chunks ADD COLUMN embedding vector(1536);
  - HNSW index: CREATE INDEX ON memory_chunks USING hnsw (embedding vector_cosine_ops);

This store delegates similarity search to the database engine via SQL,
enabling ANN search at millions-of-chunk scale.

Usage: SqliteVectorStore is the universal fallback.
       PgVectorStore is a performance optimization, not a feature gate.
"""
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from memory_engine.storage.base import VectorStore, SearchResult
from memory_engine.storage.sqlite_store import SqliteVectorStore

logger = logging.getLogger("memory_engine.storage.pgvector")


class PgVectorStore(VectorStore):
    """
    pgvector-native ANN search.

    Falls back to SqliteVectorStore methods for non-similarity operations
    (upsert, deactivate, count, get_by_source) since the ORM model is shared.
    """

    def __init__(self, db: Session, dims: int = 1536):
        self._db = db
        self._dims = dims
        self._sqlite_fallback = SqliteVectorStore(db)

    def upsert(self, chunk_id, memory_type, source_type, source_id,
               section, content, embedding, model_name, metadata, source_version=1):
        # Reuse SQLite upsert — row storage is identical
        self._sqlite_fallback.upsert(
            chunk_id, memory_type, source_type, source_id,
            section, content, embedding, model_name, metadata, source_version,
        )

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        memory_type: Optional[str] = None,
        metadata_filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        try:
            from pgvector.sqlalchemy import Vector
            from sqlalchemy import text, cast
            from models.memory import MemoryChunk

            vec_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
            raw_sql = """
                SELECT chunk_id, source_id, source_type, memory_type, section,
                       content, metadata_json, embedding_model,
                       1 - (embedding <=> CAST(:vec AS vector)) AS score
                FROM memory_chunks
                WHERE is_active = true
                {type_filter}
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :top_k
            """.format(
                type_filter="AND memory_type = :memory_type" if memory_type else ""
            )
            params = {"vec": vec_str, "top_k": top_k}
            if memory_type:
                params["memory_type"] = memory_type

            rows = self._db.execute(text(raw_sql), params).fetchall()
            results = []
            for row in rows:
                meta = json.loads(row.metadata_json or "{}")
                if metadata_filter and not all(
                    meta.get(k) == v for k, v in metadata_filter.items()
                ):
                    continue
                results.append(SearchResult(
                    chunk_id=row.chunk_id,
                    source_id=row.source_id,
                    source_type=row.source_type,
                    memory_type=row.memory_type,
                    section=row.section,
                    content=row.content,
                    score=float(row.score),
                    metadata=meta,
                    embedding_model=row.embedding_model,
                ))
            return results
        except Exception as exc:
            # Failed SQL in a transaction poisons the session; rollback before fallback.
            try:
                self._db.rollback()
            except Exception:
                pass
            logger.warning("pgvector search failed, falling back to SQLite: %s", exc)
            return self._sqlite_fallback.search(
                query_embedding, top_k, memory_type, metadata_filter
            )

    def deactivate_source(self, source_id: str) -> int:
        return self._sqlite_fallback.deactivate_source(source_id)

    def count(self, memory_type: Optional[str] = None) -> int:
        return self._sqlite_fallback.count(memory_type)

    def get_by_source(self, source_id: str) -> list[SearchResult]:
        return self._sqlite_fallback.get_by_source(source_id)
