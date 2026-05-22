"""
SME Expertise Memory.

Indexes SME profiles + historical assignment outcomes as memory chunks.
Enables semantic retrieval: "find SMEs who handled Zero Trust in banking".
"""
import logging
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from models import Stakeholder, Assignment, AuditLog
from memory_engine.chunking.splitter import DocumentChunker, RawChunk
from memory_engine.indexing.indexer import MemoryIndexer
from memory_engine.retrieval.retriever import MemoryRetriever
from memory_engine.storage.factory import get_vector_store
from memory_engine.storage.base import SearchResult
from models.memory import make_chunk_id
from memory_engine.config import DEFAULT_TOP_K, MIN_CHUNK_CHARS

logger = logging.getLogger("memory_engine.knowledge.sme")


def _build_sme_profile_text(sme: Stakeholder, success_rate: float, assignment_count: int) -> str:
    expertise = ", ".join(sme.expertise or [])
    return (
        f"SME: {sme.name} | BU: {sme.bu} | Role: {sme.role} | "
        f"Expertise: {expertise} | "
        f"Historical success rate: {int(success_rate * 100)}% | "
        f"Total assignments: {assignment_count} | "
        f"Current workload: {sme.current_workload}"
    )


class SmeMemory:
    def __init__(self, db: Session):
        self._db = db
        self._store = get_vector_store(db)

    def index_sme(self, stakeholder_id: str) -> dict:
        """Index an SME's profile and expertise as a memory chunk."""
        sme = self._db.scalar(
            select(Stakeholder).where(Stakeholder.id == stakeholder_id)
        )
        if not sme:
            return {"error": "Stakeholder not found"}

        # Compute historical success from AuditLog
        total = self._db.scalar(
            select(__import__("sqlalchemy", fromlist=["func"]).func.count(AuditLog.id))
            .where(and_(
                AuditLog.actor_id == stakeholder_id,
                AuditLog.action.in_(["approval_approved", "approval_rejected"]),
            ))
        ) or 0
        approved = self._db.scalar(
            select(__import__("sqlalchemy", fromlist=["func"]).func.count(AuditLog.id))
            .where(and_(
                AuditLog.actor_id == stakeholder_id,
                AuditLog.action == "approval_approved",
            ))
        ) or 0
        success_rate = approved / total if total > 0 else 0.5

        assignment_count = self._db.scalar(
            select(__import__("sqlalchemy", fromlist=["func"]).func.count(Assignment.id))
            .where(Assignment.stakeholder_id == stakeholder_id)
        ) or 0

        text = _build_sme_profile_text(sme, success_rate, assignment_count)
        section = "sme_profile"
        cid = make_chunk_id(stakeholder_id, section, text)

        chunk = RawChunk(
            chunk_id=cid,
            memory_type="sme",
            source_type="stakeholder",
            source_id=stakeholder_id,
            section=section,
            content=text,
            metadata={
                "stakeholder_id": stakeholder_id,
                "name": sme.name,
                "bu": sme.bu,
                "role": sme.role,
                "expertise": sme.expertise or [],
            },
        )

        indexer = MemoryIndexer(self._store)
        indexed = indexer.reindex_source(stakeholder_id, [chunk])
        return {"stakeholder_id": stakeholder_id, **indexed}

    def retrieve_experts(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        bu: Optional[str] = None,
    ) -> list[SearchResult]:
        """Find SMEs matching the query (skills, domain, expertise)."""
        meta_filter = {"bu": bu} if bu else None
        retriever = MemoryRetriever(self._store)
        return retriever.retrieve(
            query=query,
            top_k=top_k,
            memory_type="sme",
            metadata_filter=meta_filter,
        )


# Import func at the top of module properly
from sqlalchemy import func as _func
