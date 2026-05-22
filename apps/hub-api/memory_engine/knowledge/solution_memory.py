"""
Solution Pattern Memory.

Indexes reusable solution patterns extracted from winning proposals.
Enables: "suggest a SOC transformation architecture that worked for banking clients"
"""
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Proposal, Opportunity
from memory_engine.chunking.splitter import DocumentChunker, RawChunk
from memory_engine.indexing.indexer import MemoryIndexer
from memory_engine.retrieval.retriever import MemoryRetriever
from memory_engine.storage.factory import get_vector_store
from memory_engine.storage.base import SearchResult
from models.memory import make_chunk_id
from memory_engine.config import DEFAULT_TOP_K

logger = logging.getLogger("memory_engine.knowledge.solution")

# Only index proposals that are "closed_won" as solution patterns
SOLUTION_STAGES = {"closed_won", "submission", "approval"}

# Sections that represent reusable solution knowledge
_SOLUTION_SECTIONS = [
    "technical_approach", "methodology", "scope",
    "risk_matrix", "team", "pricing",
]


class SolutionMemory:
    def __init__(self, db: Session):
        self._db = db
        self._store = get_vector_store(db)

    def index_solution_pattern(self, proposal_id: str) -> dict:
        """
        Index a proposal as a solution pattern.
        Only sections with reusable engineering/commercial content are indexed.
        """
        proposal = self._db.scalar(
            select(Proposal).where(Proposal.id == proposal_id)
        )
        if not proposal:
            return {"error": "Proposal not found"}

        opp = self._db.scalar(
            select(Opportunity).where(Opportunity.id == proposal.opportunity_id)
        )

        content = proposal.content or {}
        chunks: list[RawChunk] = []

        for section in _SOLUTION_SECTIONS:
            text = content.get(section)
            if not text or not str(text).strip():
                continue
            text = str(text).strip()
            section_key = f"solution_{section}"
            cid = make_chunk_id(proposal_id, section_key, text)
            chunks.append(RawChunk(
                chunk_id=cid,
                memory_type="solution",
                source_type="proposal",
                source_id=proposal_id,
                section=section_key,
                content=text,
                metadata={
                    "proposal_id": proposal_id,
                    "rfp_type": opp.rfp_type if opp else None,
                    "stage": proposal.stage,
                    "section": section,
                    "health_score": proposal.health_score,
                },
            ))

        if not chunks:
            return {"proposal_id": proposal_id, "chunks_indexed": 0}

        indexer = MemoryIndexer(self._store)
        indexed = indexer.reindex_source(proposal_id, chunks)
        return {"proposal_id": proposal_id, **indexed}

    def suggest_patterns(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        rfp_type: Optional[str] = None,
    ) -> list[SearchResult]:
        """Retrieve solution patterns matching the query."""
        meta_filter = {"rfp_type": rfp_type} if rfp_type else None
        retriever = MemoryRetriever(self._store)
        return retriever.retrieve(
            query=query,
            top_k=top_k,
            memory_type="solution",
            metadata_filter=meta_filter,
        )
