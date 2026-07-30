"""
pgvector-backed vector store for production PostgreSQL.

Requires:
  - PostgreSQL with pgvector extension installed
  - `pip install pgvector`
  - Column: memory_chunks.embedding vector(384)  (MiniLM; see MINILM_DIMS)
  - HNSW index: CREATE INDEX ON memory_chunks USING hnsw (embedding vector_cosine_ops)
    preferably WHERE is_active

This store delegates similarity search to the database engine via SQL,
enabling ANN search at millions-of-chunk scale.

Dual-write: upsert keeps embedding_json (SQLite/tests) and also writes the
native `embedding` vector column when available.

Fail-closed: when USE_PGVECTOR is true, missing-column / missing-extension
errors are logged and re-raised so Generate does not silently degrade to
application-side cosine over JSON. Other transient failures still roll back
the poisoned session before any last-resort SQLite path.
"""
import json
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from memory_engine.config import MINILM_DIMS, USE_PGVECTOR
from memory_engine.storage.base import VectorStore, SearchResult
from memory_engine.storage.sqlite_store import SqliteVectorStore

logger = logging.getLogger("memory_engine.storage.pgvector")


def _vec_literal(embedding: list[float]) -> str:
    return "[" + ",".join(str(x) for x in embedding) + "]"


def _is_pgvector_schema_error(exc: BaseException) -> bool:
    """True when the failure indicates missing extension/column (must not degrade)."""
    msg = str(exc).lower()
    markers = (
        'column "embedding" does not exist',
        "column memory_chunks.embedding does not exist",
        'type "vector" does not exist',
        'extension "vector"',
        "could not open extension control file",
        "undefinedcolumn",
        "undefinedobject",
    )
    if any(m in msg for m in markers):
        return True
    orig = getattr(exc, "orig", None)
    pgcode = getattr(orig, "pgcode", None) if orig is not None else None
    # 42703 = undefined_column, 42704 = undefined_object (e.g. type/extension)
    if pgcode in ("42703", "42704"):
        # Only treat as schema error when message mentions embedding/vector
        return "embedding" in msg or "vector" in msg
    return False


class PgVectorStore(VectorStore):
    """
    pgvector-native ANN search.

    Falls back to SqliteVectorStore methods for non-similarity operations
    (deactivate, count, get_by_source) since the ORM model is shared.
    Upsert dual-writes embedding_json + embedding.
    """

    def __init__(self, db: Session, dims: int = MINILM_DIMS):
        self._db = db
        self._dims = dims
        self._sqlite_fallback = SqliteVectorStore(db)

    def upsert(self, chunk_id, memory_type, source_type, source_id,
               section, content, embedding, model_name, metadata, source_version=1):
        # Keep embedding_json for SQLite/tests and shared ORM helpers
        self._sqlite_fallback.upsert(
            chunk_id, memory_type, source_type, source_id,
            section, content, embedding, model_name, metadata, source_version,
        )
        # Dual-write native vector column (fail-closed on missing column/extension)
        try:
            self._db.execute(
                text(
                    "UPDATE memory_chunks "
                    "SET embedding = CAST(:vec AS vector) "
                    "WHERE chunk_id = :chunk_id"
                ),
                {"vec": _vec_literal(embedding), "chunk_id": chunk_id},
            )
            self._db.commit()
        except Exception as exc:
            try:
                self._db.rollback()
            except Exception:
                pass
            if USE_PGVECTOR and _is_pgvector_schema_error(exc):
                logger.error(
                    "pgvector dual-write failed closed (schema): embedding column/extension "
                    "missing — run alembic upgrade head on a pgvector image. Error: %s",
                    exc,
                )
                raise
            logger.warning("pgvector dual-write skipped: %s", exc)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        memory_type: Optional[str] = None,
        metadata_filter: Optional[dict] = None,
    ) -> list[SearchResult]:
        try:
            vec_str = _vec_literal(query_embedding)
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
            # Failed SQL in a transaction poisons the session; always rollback first.
            try:
                self._db.rollback()
            except Exception:
                pass

            if USE_PGVECTOR and _is_pgvector_schema_error(exc):
                logger.error(
                    "pgvector search failed closed (missing embedding column/extension). "
                    "Apply migration i5j6k7l8m9n0 on pgvector/pgvector:pg16. Error: %s",
                    exc,
                )
                raise

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
