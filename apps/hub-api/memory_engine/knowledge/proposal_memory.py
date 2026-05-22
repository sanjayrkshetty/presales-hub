"""
Proposal Memory — index and retrieve proposal knowledge.

Supports:
  - Index a proposal's content sections
  - Retrieve similar proposals by semantic query
  - Find proposals similar to a given proposal (for template reuse)
  - Section-specific retrieval (e.g. "find scope sections for banking RFPs")
"""
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Proposal, Opportunity
from memory_engine.ingestion.proposal_ingester import ingest_proposal
from memory_engine.retrieval.retriever import MemoryRetriever
from memory_engine.storage.factory import get_vector_store
from memory_engine.storage.base import SearchResult
from memory_engine.config import DEFAULT_TOP_K

logger = logging.getLogger("memory_engine.knowledge.proposal")


class ProposalMemory:
    def __init__(self, db: Session):
        self._db = db
        self._store = get_vector_store(db)

    def index(self, proposal_id: str) -> dict:
        """Index all sections of a proposal. Idempotent."""
        return ingest_proposal(proposal_id, self._db)

    def retrieve_similar(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        rfp_type: Optional[str] = None,
        section: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Find proposal chunks semantically similar to query.
        Optional filters: rfp_type, specific section.
        """
        metadata_filter = {}
        if rfp_type:
            metadata_filter["rfp_type"] = rfp_type
        if section:
            metadata_filter["section"] = section

        retriever = MemoryRetriever(self._store)
        return retriever.retrieve(
            query=query,
            top_k=top_k,
            memory_type="proposal",
            metadata_filter=metadata_filter or None,
        )

    def find_similar_proposals(
        self,
        proposal_id: str,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[dict]:
        """
        Find other proposals with similar content to the given one.
        Returns deduplicated list of {proposal_id, avg_score, top_section}.
        """
        proposal = self._db.scalar(
            select(Proposal).where(Proposal.id == proposal_id)
        )
        if not proposal:
            return []

        # Build a representative query from the proposal's exec_summary or scope
        content = proposal.content or {}
        query_text = (
            content.get("exec_summary") or
            content.get("scope") or
            content.get("technical_approach") or
            ""
        )
        if not query_text:
            return []

        retriever = MemoryRetriever(self._store)
        results = retriever.retrieve(
            query=str(query_text)[:500],
            top_k=top_k * 3,
            memory_type="proposal",
        )

        # Aggregate by proposal_id (exclude self)
        agg: dict[str, list[float]] = {}
        top_section: dict[str, str] = {}
        for r in results:
            pid = r.metadata.get("proposal_id") or r.source_id
            if pid == proposal_id:
                continue
            agg.setdefault(pid, []).append(r.score)
            if pid not in top_section:
                top_section[pid] = r.section or "unknown"

        scored = [
            {
                "proposal_id": pid,
                "avg_score": round(sum(scores) / len(scores), 4),
                "top_section": top_section[pid],
                "matching_chunks": len(scores),
            }
            for pid, scores in agg.items()
        ]
        scored.sort(key=lambda x: x["avg_score"], reverse=True)
        return scored[:top_k]
