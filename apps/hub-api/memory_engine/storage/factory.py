"""Factory: returns the appropriate VectorStore for the current DB backend."""
from sqlalchemy.orm import Session

from memory_engine.config import USE_PGVECTOR
from memory_engine.storage.base import VectorStore


def get_vector_store(db: Session) -> VectorStore:
    if USE_PGVECTOR:
        from memory_engine.storage.pgvector_store import PgVectorStore
        return PgVectorStore(db)
    from memory_engine.storage.sqlite_store import SqliteVectorStore
    return SqliteVectorStore(db)
