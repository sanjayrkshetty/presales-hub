"""
Approval Rationale Ingester.

Indexes approval decision notes for institutional memory.
Preserves: who decided, what stage, what rationale, what outcome.
Enables: "what were rejection reasons for security_review in banking proposals?"
"""
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Approval, Proposal
from memory_engine.chunking.splitter import ApprovalChunker
from memory_engine.indexing.indexer import MemoryIndexer
from memory_engine.storage.factory import get_vector_store

logger = logging.getLogger("memory_engine.ingestion.approval")


def ingest_approval(approval_id: str, db: Session) -> dict:
    """Index the decision note of a single approval."""
    approval = db.scalar(select(Approval).where(Approval.id == approval_id))
    if not approval:
        return {"error": "Approval not found", "approval_id": approval_id}

    # Get proposal context for metadata
    proposal = db.scalar(
        select(Proposal).where(Proposal.id == approval.proposal_id)
    ) if approval.proposal_id else None

    metadata = {
        "approval_id": approval_id,
        "proposal_id": approval.proposal_id,
        "stage": approval.stage,
        "status": approval.status,
        "actor_id": approval.approver_id,
    }

    chunker = ApprovalChunker()
    chunk = chunker.chunk(
        approval_id=approval_id,
        proposal_id=approval.proposal_id or "",
        stage=approval.stage,
        status=approval.status or "",
        decision_note=approval.decision_note,
        actor_id=approval.approver_id,
        metadata=metadata,
    )

    if not chunk:
        return {"approval_id": approval_id, "chunks_indexed": 0, "reason": "no_content"}

    store = get_vector_store(db)
    indexer = MemoryIndexer(store)
    indexed = indexer.index_chunks([chunk])
    return {"approval_id": approval_id, "chunks_indexed": indexed}


def ingest_proposal_approvals(proposal_id: str, db: Session) -> dict:
    """Index all approvals for a proposal in one call."""
    approvals = db.scalars(
        select(Approval).where(Approval.proposal_id == proposal_id)
    ).all()
    total = 0
    for appr in approvals:
        if appr.decision_note or appr.status in {"rejected", "escalated"}:
            result = ingest_approval(appr.id, db)
            total += result.get("chunks_indexed", 0)
    return {"proposal_id": proposal_id, "approvals_indexed": total}
