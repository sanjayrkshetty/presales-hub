"""
MemoryChunk — primary persistence unit for the Enterprise Memory Engine.

Each chunk represents one semantically coherent piece of organizational
knowledge: a proposal section, an approval rationale, a customer pattern,
a delivery lesson, etc.

Design decisions:
  - embedding_json: stored as TEXT (JSON array of floats) so it works in
    both SQLite (dev/test) and PostgreSQL.  A production migration can
    ALTER this column to vector(N) once pgvector is available.
  - chunk_id: SHA-256 of (source_id + section + content) — enables
    idempotent re-indexing without duplicates.
  - is_active: soft-delete for safe re-indexing; stale chunks are
    deactivated before new embeddings are inserted.
  - metadata_json: arbitrary key-value pairs for metadata pre-filtering
    (client_id, stage, rfp_type, role, etc.) without schema churn.
"""
import hashlib
import json
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def make_chunk_id(source_id: str, section: str, content: str) -> str:
    """Deterministic SHA-256 of the chunk's identity. Used for dedup."""
    raw = f"{source_id}::{section}::{content[:512]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:48]


class MemoryChunk(Base):
    """One semantically coherent unit of organizational knowledge."""
    __tablename__ = "memory_chunks"

    id = Column(String(36), primary_key=True, default=_uuid)
    chunk_id = Column(String(48), unique=True, nullable=False, index=True)

    # Provenance
    memory_type = Column(Text, nullable=False, index=True)
    # proposal / approval / sme / customer / solution / delivery / audit
    source_type = Column(Text, nullable=False)
    # proposal / approval / audit_log / document / stakeholder / opportunity
    source_id = Column(String(255), nullable=False, index=True)
    source_version = Column(Integer, default=1, nullable=False)

    # Content
    section = Column(Text, nullable=True)    # e.g. "exec_summary", "decision_note"
    content = Column(Text, nullable=False)   # original text

    # Vector (JSON for SQLite; ALTER to vector(N) for pgvector in production)
    embedding_json = Column(Text, nullable=True)   # JSON: [0.12, -0.34, ...]
    embedding_model = Column(Text, default="local-hash-v1", nullable=False)
    embedding_dims = Column(Integer, nullable=True)

    # Metadata filters (serialized dict)
    metadata_json = Column(Text, default="{}", nullable=False)
    # Keys: client_id, rfp_type, stage, role, opportunity_id, proposal_id, actor_id

    # Lifecycle
    indexed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("idx_memory_type_active", "memory_type", "is_active"),
        Index("idx_memory_source", "source_type", "source_id"),
    )

    # ── helpers ──────────────────────────────────────────────────────────────

    def get_embedding(self) -> list[float]:
        if self.embedding_json:
            return json.loads(self.embedding_json)
        return []

    def set_embedding(self, vec: list[float], model: str) -> None:
        self.embedding_json = json.dumps(vec)
        self.embedding_model = model
        self.embedding_dims = len(vec)

    def get_metadata(self) -> dict:
        try:
            return json.loads(self.metadata_json or "{}")
        except Exception:
            return {}

    def set_metadata(self, meta: dict) -> None:
        self.metadata_json = json.dumps(meta)

    def to_result(self, score: float = 0.0) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "memory_type": self.memory_type,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "section": self.section,
            "content": self.content,
            "metadata": self.get_metadata(),
            "score": round(score, 4),
            "indexed_at": self.indexed_at.isoformat(),
            "embedding_model": self.embedding_model,
        }
