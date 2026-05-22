"""
Approval Rationale Memory.

Indexes approval decisions + rejection/escalation reasoning.
Enables: "what caused security review rejections in compliance proposals?"
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session

from memory_engine.ingestion.approval_ingester import ingest_proposal_approvals, ingest_approval
from memory_engine.retrieval.retriever import MemoryRetriever
from memory_engine.storage.factory import get_vector_store
from memory_engine.storage.base import SearchResult
from memory_engine.config import DEFAULT_TOP_K

logger = logging.getLogger("memory_engine.knowledge.approval")


class ApprovalMemory:
    def __init__(self, db: Session):
        self._db = db
        self._store = get_vector_store(db)

    def index_approval(self, approval_id: str) -> dict:
        return ingest_approval(approval_id, self._db)

    def index_proposal_approvals(self, proposal_id: str) -> dict:
        return ingest_proposal_approvals(proposal_id, self._db)

    def retrieve_rationale(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        stage: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Retrieve similar approval rationale.
        E.g.: "scope creep risk in security_review rejection"
        """
        meta_filter = {}
        if stage:
            meta_filter["stage"] = stage
        if status:
            meta_filter["status"] = status

        retriever = MemoryRetriever(self._store)
        return retriever.retrieve(
            query=query,
            top_k=top_k,
            memory_type="approval",
            metadata_filter=meta_filter or None,
        )
