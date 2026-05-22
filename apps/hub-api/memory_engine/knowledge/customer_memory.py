"""
Customer Intelligence Memory.

Indexes customer/client context: opportunity titles, RFP types,
stage history, and any notes — to enable retrieval of:
  "what patterns appear in HDFC Bank engagements?"
  "which customers frequently escalate security reviews?"
"""
import logging
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Opportunity
from models.opportunity import Client
from memory_engine.chunking.splitter import DocumentChunker, RawChunk
from memory_engine.indexing.indexer import MemoryIndexer
from memory_engine.retrieval.retriever import MemoryRetriever
from memory_engine.storage.factory import get_vector_store
from memory_engine.storage.base import SearchResult
from models.memory import make_chunk_id
from memory_engine.config import DEFAULT_TOP_K, MIN_CHUNK_CHARS

logger = logging.getLogger("memory_engine.knowledge.customer")


def _build_opportunity_text(opp: Opportunity, client_name: str) -> str:
    parts = [
        f"Customer: {client_name}",
        f"Opportunity: {opp.title}",
        f"RFP type: {opp.rfp_type or 'unspecified'}",
        f"Stage: {opp.stage}",
        f"Deal value: {opp.deal_value_cr or 'N/A'} Cr",
        f"Win probability: {opp.win_probability}%",
    ]
    return " | ".join(parts)


class CustomerMemory:
    def __init__(self, db: Session):
        self._db = db
        self._store = get_vector_store(db)

    def index_opportunity(self, opportunity_id: str) -> dict:
        """Index an opportunity as a customer intelligence chunk."""
        opp = self._db.scalar(
            select(Opportunity).where(Opportunity.id == opportunity_id)
        )
        if not opp:
            return {"error": "Opportunity not found"}

        client = self._db.scalar(
            select(Client).where(Client.id == opp.client_id)
        ) if opp.client_id else None
        client_name = client.name if client else "Unknown"

        text = _build_opportunity_text(opp, client_name)
        section = "opportunity_profile"
        cid = make_chunk_id(opportunity_id, section, text)

        chunk = RawChunk(
            chunk_id=cid,
            memory_type="customer",
            source_type="opportunity",
            source_id=opportunity_id,
            section=section,
            content=text,
            metadata={
                "opportunity_id": opportunity_id,
                "client_id": opp.client_id,
                "client_name": client_name,
                "rfp_type": opp.rfp_type,
                "stage": opp.stage,
            },
        )

        indexer = MemoryIndexer(self._store)
        indexed = indexer.reindex_source(opportunity_id, [chunk])
        return {"opportunity_id": opportunity_id, **indexed}

    def retrieve_patterns(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        client_id: Optional[str] = None,
    ) -> list[SearchResult]:
        """Retrieve customer patterns relevant to query."""
        meta_filter = {"client_id": client_id} if client_id else None
        retriever = MemoryRetriever(self._store)
        return retriever.retrieve(
            query=query,
            top_k=top_k,
            memory_type="customer",
            metadata_filter=meta_filter,
        )
