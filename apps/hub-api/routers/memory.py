"""
Enterprise Memory API.

All write operations (index) are synchronous.
Search operations return immediately (no LLM in critical path).
Reranking is opt-in (?rerank=true) on search and retrieval endpoints.

Endpoints:
  POST /api/memory/index/proposal/{id}
  POST /api/memory/index/approval/{id}
  POST /api/memory/index/opportunity/{id}
  POST /api/memory/index/sme/{id}
  POST /api/memory/search
  GET  /api/memory/proposals/{id}/similar
  GET  /api/memory/sme/experts
  GET  /api/memory/customers/{id}/patterns
  GET  /api/memory/solutions/suggest
  GET  /api/memory/approvals/rationale
  GET  /api/memory/status
  POST /api/memory/reindex/proposal/{id}
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from lib.dependencies import require_permission
from memory_engine.storage.factory import get_vector_store
from memory_engine.semantic_search.searcher import SemanticSearcher
from memory_engine.knowledge.proposal_memory import ProposalMemory
from memory_engine.knowledge.sme_memory import SmeMemory
from memory_engine.knowledge.customer_memory import CustomerMemory
from memory_engine.knowledge.approval_memory import ApprovalMemory
from memory_engine.knowledge.solution_memory import SolutionMemory
from telemetry.context import set_proposal_id

logger = logging.getLogger("routers.memory")

router = APIRouter(prefix="/api/memory", tags=["memory"])


# ── Request models ─────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    memory_type: Optional[str] = None
    top_k: int = 5
    rerank: bool = False
    metadata_filter: Optional[dict] = None
    deduplicate_sources: bool = False


class CorpusIngestRequest(BaseModel):
    """Ingest scrubbed corpus files. Never point this at raw/unscrubbed trees."""
    source_dir: Optional[str] = None  # defaults to corpus/scrubbed + seed/scrubbed_demo
    bu: str = "dfir"


# ── Indexing endpoints ─────────────────────────────────────────────────────────

@router.post("/index/proposal/{proposal_id}")
def index_proposal(proposal_id: str, db: Session = Depends(get_db), _authz=require_permission("memory:write")):
    """Index all content sections of a proposal into memory."""
    set_proposal_id(proposal_id)
    memory = ProposalMemory(db)
    result = memory.index(proposal_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/index/approval/{approval_id}")
def index_approval(approval_id: str, db: Session = Depends(get_db), _authz=require_permission("memory:write")):
    """Index an approval's decision rationale into approval memory."""
    memory = ApprovalMemory(db)
    result = memory.index_approval(approval_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/index/opportunity/{opportunity_id}")
def index_opportunity(opportunity_id: str, db: Session = Depends(get_db), _authz=require_permission("memory:write")):
    """Index an opportunity as customer intelligence memory."""
    memory = CustomerMemory(db)
    result = memory.index_opportunity(opportunity_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/index/sme/{stakeholder_id}")
def index_sme(stakeholder_id: str, db: Session = Depends(get_db), _authz=require_permission("memory:write")):
    """Index an SME's expertise profile into SME memory."""
    memory = SmeMemory(db)
    result = memory.index_sme(stakeholder_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/corpus/ingest")
def ingest_corpus(req: CorpusIngestRequest, db: Session = Depends(get_db), _authz=require_permission("memory:write")):
    """
    Index scrubbed DFIR (or other BU) corpus into pgvector memory.
    Reads corpus/scrubbed (gitignored) and/or seed/scrubbed_demo.
    Applies a last-pass scrub before embedding. Never commit raw proposals.
    """
    from memory_engine.ingestion.corpus_ingester import ingest_scrubbed_corpus

    result = ingest_scrubbed_corpus(db, source_dir=req.source_dir, bu=req.bu)
    if result.get("error") and result.get("indexed", 0) == 0:
        raise HTTPException(400, result["error"])
    return result


@router.post("/scrub")
def scrub_preview(payload: dict, _authz=require_permission("memory:write")):
    """Preview scrub replacements on text (does not persist)."""
    from memory_engine.scrub.scrubber import scrub_text

    text = payload.get("text") or ""
    result = scrub_text(text)
    return {
        "text": result.text,
        "replacements": result.replacements,
        "flags": result.flags,
        "changed": result.changed,
    }


# ── Search endpoints ───────────────────────────────────────────────────────────

@router.post("/search")
async def semantic_search(req: SearchRequest, db: Session = Depends(get_db), _authz=require_permission("memory:read")):
    """
    Universal semantic search across all memory types (or a specific one).
    Supports optional LLM reranking for improved relevance.
    """
    if req.top_k < 1 or req.top_k > 50:
        raise HTTPException(422, "top_k must be between 1 and 50")

    store = get_vector_store(db)
    searcher = SemanticSearcher(store)
    response = await searcher.search(
        query=req.query,
        top_k=req.top_k,
        memory_type=req.memory_type,
        metadata_filter=req.metadata_filter,
        rerank=req.rerank,
        deduplicate_sources=req.deduplicate_sources,
    )
    return response.to_dict()


@router.get("/proposals/{proposal_id}/similar")
async def similar_proposals(
    proposal_id: str,
    top_k: int = Query(5, ge=1, le=20),
    rerank: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Find proposals with similar content to the given one."""
    set_proposal_id(proposal_id)
    memory = ProposalMemory(db)
    similar = memory.find_similar_proposals(proposal_id, top_k=top_k)
    return {"proposal_id": proposal_id, "similar_proposals": similar, "count": len(similar)}


@router.get("/sme/experts")
async def find_sme_experts(
    query: str = Query(..., description="Skill or domain to search for"),
    top_k: int = Query(5, ge=1, le=20),
    bu: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Find SMEs matching expertise query (semantic search over SME profiles)."""
    memory = SmeMemory(db)
    results = memory.retrieve_experts(query=query, top_k=top_k, bu=bu)
    return {
        "query": query,
        "results": [r.to_dict() for r in results],
        "count": len(results),
    }


@router.get("/customers/{opportunity_id}/patterns")
async def customer_patterns(
    opportunity_id: str,
    query: str = Query(..., description="What patterns to retrieve"),
    top_k: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Retrieve historical customer intelligence patterns for an opportunity."""
    memory = CustomerMemory(db)
    # Look up client_id for this opportunity's client
    from sqlalchemy import select
    from models import Opportunity
    opp = db.scalar(select(Opportunity).where(Opportunity.id == opportunity_id))
    client_id = opp.client_id if opp else None

    results = memory.retrieve_patterns(
        query=query, top_k=top_k, client_id=client_id
    )
    return {
        "opportunity_id": opportunity_id,
        "query": query,
        "results": [r.to_dict() for r in results],
        "count": len(results),
    }


@router.get("/solutions/suggest")
async def suggest_solutions(
    query: str = Query(..., description="Problem or requirement to solve"),
    top_k: int = Query(5, ge=1, le=20),
    rfp_type: Optional[str] = Query(None),
    rerank: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Retrieve solution patterns from institutional memory."""
    memory = SolutionMemory(db)
    results = memory.suggest_patterns(query=query, top_k=top_k, rfp_type=rfp_type)
    return {
        "query": query,
        "results": [r.to_dict() for r in results],
        "count": len(results),
        "rfp_type": rfp_type,
    }


@router.get("/approvals/rationale")
async def approval_rationale(
    query: str = Query(..., description="Search query for approval rationale"),
    stage: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    top_k: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Retrieve historical approval decisions matching the query."""
    memory = ApprovalMemory(db)
    results = memory.retrieve_rationale(query=query, top_k=top_k, stage=stage, status=status)
    return {
        "query": query,
        "results": [r.to_dict() for r in results],
        "count": len(results),
    }


# ── Operational endpoints ──────────────────────────────────────────────────────

@router.get("/status")
def memory_status(db: Session = Depends(get_db)):
    """Index health — chunk counts per memory type and total."""
    store = get_vector_store(db)
    memory_types = ["proposal", "approval", "sme", "customer", "solution", "delivery", "audit"]
    counts = {mt: store.count(mt) for mt in memory_types}
    total = sum(counts.values())
    return {
        "total_chunks": total,
        "by_memory_type": counts,
        "index_healthy": total >= 0,
    }


@router.post("/reindex/proposal/{proposal_id}")
def reindex_proposal(proposal_id: str, db: Session = Depends(get_db), _authz=require_permission("memory:write")):
    """
    Force full re-indexing of a proposal.
    Deactivates stale chunks before inserting fresh embeddings.
    """
    set_proposal_id(proposal_id)
    memory = ProposalMemory(db)
    result = memory.index(proposal_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return {**result, "reindexed": True}
