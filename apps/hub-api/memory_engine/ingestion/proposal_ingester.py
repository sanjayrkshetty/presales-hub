"""
Proposal Ingester.

Reads a Proposal ORM object and its linked Opportunity/Client,
generates RawChunks for every non-empty section, and calls MemoryIndexer.

Metadata attached to each chunk (for pre-filtering):
  proposal_id, opportunity_id, client_id, rfp_type, stage, client_name
"""
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Proposal, Opportunity
from memory_engine.chunking.splitter import ProposalChunker
from memory_engine.indexing.indexer import MemoryIndexer
from memory_engine.storage.factory import get_vector_store

logger = logging.getLogger("memory_engine.ingestion.proposal")


def ingest_proposal(proposal_id: str, db: Session) -> dict:
    """
    Index all content sections of a proposal.
    Returns {proposal_id, chunks_indexed, source_version}.
    """
    proposal = db.scalar(select(Proposal).where(Proposal.id == proposal_id))
    if not proposal:
        return {"error": "Proposal not found", "proposal_id": proposal_id}

    opp = db.scalar(select(Opportunity).where(Opportunity.id == proposal.opportunity_id))

    metadata = {
        "proposal_id": proposal_id,
        "opportunity_id": proposal.opportunity_id,
        "stage": proposal.stage,
        "rfp_type": opp.rfp_type if opp else None,
        "client_id": opp.client_id if opp else None,
    }

    chunker = ProposalChunker()
    chunks = chunker.chunk(
        proposal_id=proposal_id,
        content=proposal.content or {},
        metadata=metadata,
        source_version=proposal.version or 1,
    )

    if not chunks:
        logger.info("No indexable content in proposal %s", proposal_id)
        return {"proposal_id": proposal_id, "chunks_indexed": 0}

    store = get_vector_store(db)
    indexer = MemoryIndexer(store)
    result = indexer.reindex_source(proposal_id, chunks)
    logger.info("Indexed proposal %s: %s chunks", proposal_id, result["indexed"])
    return {**result, "proposal_id": proposal_id}
