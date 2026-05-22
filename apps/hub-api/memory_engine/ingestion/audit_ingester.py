"""
Audit Log Ingester.

Indexes AuditLog entries as delivery lessons and escalation history.
Useful for: "what happened in past security_review escalations?"
"""
import logging
import json
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from models import AuditLog
from memory_engine.chunking.splitter import DocumentChunker, RawChunk
from memory_engine.indexing.indexer import MemoryIndexer
from memory_engine.storage.factory import get_vector_store
from models.memory import make_chunk_id
from memory_engine.config import MIN_CHUNK_CHARS

logger = logging.getLogger("memory_engine.ingestion.audit")

_INDEXABLE_ACTIONS = {
    "stage_transition", "sme_assigned", "approval_rejected",
    "approval_escalated", "sla_breach", "unauthorized_approval_attempt",
}


def _audit_to_text(row: AuditLog) -> str:
    parts = [f"Action: {row.action}"]
    if row.from_state:
        parts.append(f"From: {row.from_state}")
    if row.to_state:
        parts.append(f"To: {row.to_state}")
    if row.metadata:
        meta = row.metadata if isinstance(row.metadata, dict) else {}
        for k, v in meta.items():
            if v and isinstance(v, str) and len(v) < 200:
                parts.append(f"{k}: {v}")
    return " | ".join(parts)


def ingest_audit_logs(
    entity_id: str,
    entity_type: str,
    db: Session,
    memory_type: str = "delivery",
) -> dict:
    """Index audit log entries for an entity."""
    rows = db.scalars(
        select(AuditLog).where(
            and_(
                AuditLog.entity_id == entity_id,
                AuditLog.entity_type == entity_type,
                AuditLog.action.in_(_INDEXABLE_ACTIONS),
            )
        )
    ).all()

    chunks: list[RawChunk] = []
    for row in rows:
        text = _audit_to_text(row)
        if len(text) < MIN_CHUNK_CHARS:
            continue
        section = f"audit_{row.action}"
        cid = make_chunk_id(row.id, section, text)
        chunks.append(RawChunk(
            chunk_id=cid,
            memory_type=memory_type,
            source_type="audit_log",
            source_id=row.id,
            section=section,
            content=text,
            metadata={
                "entity_id": entity_id,
                "entity_type": entity_type,
                "action": row.action,
                "actor_id": row.actor_id,
            },
        ))

    if not chunks:
        return {"entity_id": entity_id, "chunks_indexed": 0}

    store = get_vector_store(db)
    indexer = MemoryIndexer(store)
    indexed = indexer.index_chunks(chunks)
    return {"entity_id": entity_id, "chunks_indexed": indexed}
