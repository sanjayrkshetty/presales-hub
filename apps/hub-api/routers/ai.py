import os
import json
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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
