import os
import json
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.database import get_db
from lib.dependencies import require_permission
from models import Proposal, Opportunity

router = APIRouter(prefix="/api/ai", tags=["ai"])


class GenerateRequest(BaseModel):
    opportunity_id: str
    sections: list[str] | None = None


class HealthScoreRequest(BaseModel):
    proposal_id: str


class GenerateDocxRequest(BaseModel):
    brief: str = Field("", description="Optional drafting brief (will be scrubbed before Groq)")
    bu: str = Field("dfir", description="Content pack filter: dfir|vapt|grc|shared")
    sections: list[str] | None = None
    as_json: bool = Field(
        False,
        description="If true, return JSON metadata + base64 docx instead of binary download",
    )


@router.post("/health-score")
def compute_health_score(req: HealthScoreRequest, db: Session = Depends(get_db), _authz=require_permission("proposal:write")):
    proposal = db.scalar(
        select(Proposal)
        .where(Proposal.id == req.proposal_id)
    )
    if not proposal:
        raise HTTPException(404, "Proposal not found")

    content = proposal.content or {}
    score = 0

    # Heuristic scoring (real AI scoring would call Groq/Claude)
    if content.get("exec_summary"):
        score += 20
    if content.get("scope"):
        score += 20
    if content.get("pricing"):
        score += 20
    if content.get("timeline"):
        score += 15
    if content.get("risk_matrix"):
        score += 15
    if content.get("team"):
        score += 10

    # Stage bonus
    stage_scores = {
        "intake": 10, "qualification": 25, "sme_assignment": 35,
        "drafting": 50, "technical_review": 65, "security_review": 70,
        "delivery_review": 70, "finance_review": 80, "legal_review": 85,
        "approval": 90, "submission": 95,
    }
    stage_baseline = stage_scores.get(proposal.stage, 0)
    final_score = max(score, stage_baseline)

    proposal.health_score = min(99, final_score)
    db.commit()

    return {"proposal_id": req.proposal_id, "health_score": proposal.health_score, "breakdown": {
        "exec_summary": bool(content.get("exec_summary")),
        "scope": bool(content.get("scope")),
        "pricing": bool(content.get("pricing")),
        "timeline": bool(content.get("timeline")),
    }}


@router.post("/generate-proposal")
async def generate_proposal(req: GenerateRequest, db: Session = Depends(get_db), _authz=require_permission("copilot:use")):
    opp = db.scalar(
        select(Opportunity)
        .where(Opportunity.id == req.opportunity_id)
    )
    if not opp:
        raise HTTPException(404, "Opportunity not found")

    proposal_engine_url = os.getenv("PROPOSAL_ENGINE_URL", "http://localhost:8004")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{proposal_engine_url}/generate", json={
                "rfp_type": opp.rfp_type,
                "client_name": opp.client.name if opp.client else "",
                "deal_value_cr": float(opp.deal_value_cr or 0),
                "sections": req.sections or ["exec_summary", "scope", "pricing"],
            })
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        raise HTTPException(503, "Proposal engine unavailable")


@router.post("/proposals/{proposal_id}/generate-docx")
async def generate_docx(
    proposal_id: str,
    req: GenerateDocxRequest,
    db: Session = Depends(get_db),
    _authz=require_permission("copilot:use"),
):
    """
    War-room Generate → editable .docx grounded on scrubbed DFIR RAG.

    Chat: Groq on scrubbed text only. Embeddings: local MiniLM.
    If Groq is unavailable, returns a retrieval-grounded template docx.
    """
    import base64
    from memory_engine.generate_docx import generate_proposal_docx

    try:
        docx_bytes, meta = await generate_proposal_docx(
            db,
            proposal_id,
            brief=req.brief,
            bu=req.bu,
            sections=req.sections,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc

    if req.as_json:
        return {
            **meta,
            "docx_base64": base64.b64encode(docx_bytes).decode("ascii"),
            "filename": f"proposal-{proposal_id[:8]}-draft.docx",
        }

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="proposal-{proposal_id[:8]}-draft.docx"',
            "X-Generate-Mode": meta.get("mode", ""),
            "X-Retrieved-Chunks": str(meta.get("retrieved_chunks", 0)),
        },
    )
