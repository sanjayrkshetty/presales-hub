"""
AI Copilot & Workflow Assistant API.

All write operations are async (LLM calls in path).
All responses include grounding, evaluation, and safety metadata for auditability.

Endpoints:
  POST /api/copilot/rfp/analyze
  POST /api/copilot/proposals/{id}/draft-section
  POST /api/copilot/proposals/{id}/brief
  POST /api/copilot/proposals/{id}/risks
  POST /api/copilot/proposals/{id}/compliance-gap
  POST /api/copilot/proposals/{id}/sme-recommend
  POST /api/copilot/proposals/{id}/workflow-guide
  POST /api/copilot/approvals/{id}/explain
  POST /api/copilot/solutions/suggest
  GET  /api/copilot/prompts
  GET  /api/copilot/status
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from lib.dependencies import require_permission
from copilot_engine.providers.mock_provider import MockLLMProvider

# Import all prompt modules to populate registry at startup
import copilot_engine.prompts.rfp_analysis         # noqa: F401
import copilot_engine.prompts.proposal_drafting     # noqa: F401
import copilot_engine.prompts.executive_briefing    # noqa: F401
import copilot_engine.prompts.approval_assist       # noqa: F401
import copilot_engine.prompts.compliance_gap        # noqa: F401
import copilot_engine.prompts.risk_explanation      # noqa: F401
import copilot_engine.prompts.sme_recommendation    # noqa: F401
import copilot_engine.prompts.solution_architecture # noqa: F401
import copilot_engine.prompts.workflow_guidance     # noqa: F401

from copilot_engine.prompts.registry import registry as prompt_registry
from copilot_engine.session_memory.session_store import session_store

logger = logging.getLogger("routers.copilot")
router = APIRouter(prefix="/api/copilot", tags=["copilot"])


# ── Request models ─────────────────────────────────────────────────────────────

class RfpAnalyzeRequest(BaseModel):
    rfp_text: str = Field(..., min_length=10)
    session_id: Optional[str] = None


class DraftSectionRequest(BaseModel):
    section: str = Field(..., description="Proposal section name (e.g. exec_summary, scope)")
    user_query: Optional[str] = Field(None, description="Additional guidance for the draft")
    session_id: Optional[str] = None


class ComplianceGapRequest(BaseModel):
    rfp_requirements: str = Field(..., min_length=10)
    session_id: Optional[str] = None


class SmeRecommendRequest(BaseModel):
    user_query: str = Field(..., description="Skill or domain to match")
    top_k: int = Field(5, ge=1, le=20)


class WorkflowGuideRequest(BaseModel):
    user_query: str = Field(..., description="Current situation or question")
    session_id: Optional[str] = None


class SolutionSuggestRequest(BaseModel):
    requirements: str = Field(..., min_length=10)
    rfp_type: Optional[str] = None
    opportunity_context: Optional[str] = None


def _get_provider():
    """Use mock provider when no real API key is configured."""
    from copilot_engine.providers.factory import get_llm_provider
    return get_llm_provider()


# ── RFP Analysis ──────────────────────────────────────────────────────────────

@router.post("/rfp/analyze")
async def analyze_rfp(req: RfpAnalyzeRequest, db: Session = Depends(get_db), _authz=require_permission("copilot:use")):
    """Analyze an RFP document and extract structured intelligence."""
    from copilot_engine.assistants.rfp_analyst import RfpAnalyst
    analyst = RfpAnalyst(db, _get_provider())
    result = await analyst.analyze(req.rfp_text, session_id=req.session_id)
    return result.to_dict()


# ── Proposal Copilots ─────────────────────────────────────────────────────────

@router.post("/proposals/{proposal_id}/draft-section")
async def draft_section(
    proposal_id: str,
    req: DraftSectionRequest,
    db: Session = Depends(get_db),
    _authz=require_permission("copilot:use"),
):
    """Draft a proposal section grounded in historical proposals."""
    from copilot_engine.assistants.proposal_drafter import ProposalDrafter
    drafter = ProposalDrafter(db, _get_provider())
    result = await drafter.draft_section(
        proposal_id=proposal_id,
        section=req.section,
        user_query=req.user_query or "",
    )
    return result.to_dict()


@router.post("/proposals/{proposal_id}/brief")
async def executive_brief(proposal_id: str, db: Session = Depends(get_db), _authz=require_permission("copilot:use")):
    """Generate a VP-ready executive briefing for the proposal."""
    from copilot_engine.assistants.executive_briefing import ExecutiveBriefingCopilot
    copilot = ExecutiveBriefingCopilot(db, _get_provider())
    result = await copilot.brief(proposal_id)
    return result.to_dict()


@router.post("/proposals/{proposal_id}/risks")
async def explain_risks(proposal_id: str, db: Session = Depends(get_db), _authz=require_permission("copilot:use")):
    """Explain proposal risks in plain language with mitigations."""
    from copilot_engine.assistants.executive_briefing import ExecutiveBriefingCopilot
    copilot = ExecutiveBriefingCopilot(db, _get_provider())
    result = await copilot.explain_risks(proposal_id)
    return result.to_dict()


@router.post("/proposals/{proposal_id}/compliance-gap")
async def compliance_gap(
    proposal_id: str,
    req: ComplianceGapRequest,
    db: Session = Depends(get_db),
    _authz=require_permission("copilot:use"),
):
    """Identify compliance gaps between RFP requirements and proposal content."""
    from copilot_engine.context_builders.proposal_context import ProposalContextBuilder
    from copilot_engine.retrieval.context_retriever import ContextRetriever
    from copilot_engine.orchestration.copilot_runner import CopilotRunner

    ctx = ProposalContextBuilder(db).build(proposal_id)
    if not ctx:
        raise HTTPException(404, f"Proposal {proposal_id} not found")

    content = ctx.get("content") or {}
    proposal_text = "\n\n".join(
        f"[{section}]\n{text}"
        for section, text in content.items()
        if text
    ) or "No proposal content available."

    chunks = ContextRetriever(db).retrieve_for_proposal(req.rfp_requirements, top_k=4)
    memory_context = ContextRetriever.format_as_context(chunks)

    runner = CopilotRunner(db, _get_provider())
    result = await runner.run(
        prompt_name="compliance_gap_v1",
        prompt_vars={
            "rfp_requirements": req.rfp_requirements[:2000],
            "proposal_content": proposal_text[:2000],
            "memory_context": memory_context,
        },
        context_chunks=chunks,
        expected_json_fields=["requirements_coverage", "critical_gaps", "compliance_score", "recommendations"],
    )
    return result.to_dict()


@router.post("/proposals/{proposal_id}/sme-recommend")
async def sme_recommend(
    proposal_id: str,
    req: SmeRecommendRequest,
    db: Session = Depends(get_db),
    _authz=require_permission("copilot:use"),
):
    """Explain SME staffing recommendations for this proposal."""
    from memory_engine.knowledge.sme_memory import SmeMemory
    from copilot_engine.context_builders.proposal_context import ProposalContextBuilder
    from copilot_engine.orchestration.copilot_runner import CopilotRunner

    ctx = ProposalContextBuilder(db).build(proposal_id)
    if not ctx:
        raise HTTPException(404, f"Proposal {proposal_id} not found")

    # Get SME candidates from memory engine
    sme_memory = SmeMemory(db)
    candidates = sme_memory.retrieve_experts(query=req.user_query, top_k=req.top_k)
    candidates_text = "\n".join(
        f"[Rank {i+1}] SME: {c.source_id} | Score: {c.score:.3f} | {c.content[:300]}"
        for i, c in enumerate(candidates)
    ) or "No SME candidates found in memory."

    proposal_ctx_text = ProposalContextBuilder.to_text(ctx)

    runner = CopilotRunner(db, _get_provider())
    result = await runner.run(
        prompt_name="sme_recommendation_v1",
        prompt_vars={
            "sme_candidates": candidates_text,
            "proposal_context": proposal_ctx_text,
        },
        expected_json_fields=["recommendations", "coverage_analysis", "staffing_risk"],
    )
    return result.to_dict()


@router.post("/proposals/{proposal_id}/workflow-guide")
async def workflow_guide(
    proposal_id: str,
    req: WorkflowGuideRequest,
    db: Session = Depends(get_db),
    _authz=require_permission("copilot:use"),
):
    """Get workflow navigation guidance for the current proposal state."""
    from copilot_engine.context_builders.proposal_context import ProposalContextBuilder
    from copilot_engine.retrieval.context_retriever import ContextRetriever
    from copilot_engine.orchestration.copilot_runner import CopilotRunner

    ctx = ProposalContextBuilder(db).build(proposal_id)
    if not ctx:
        raise HTTPException(404, f"Proposal {proposal_id} not found")

    workflow_text = ProposalContextBuilder.to_text(ctx)
    chunks = ContextRetriever(db).retrieve_for_workflow(req.user_query, top_k=4)
    memory_context = ContextRetriever.format_as_context(chunks)

    runner = CopilotRunner(db, _get_provider())
    result = await runner.run(
        prompt_name="workflow_guidance_v1",
        prompt_vars={
            "proposal_id": proposal_id,
            "workflow_context": workflow_text,
            "memory_context": memory_context,
        },
        user_query=req.user_query,
        context_chunks=chunks,
        expected_json_fields=["current_status", "next_steps", "blockers", "risk_factors", "timeline_assessment"],
    )
    return result.to_dict()


# ── Approval Assistant ─────────────────────────────────────────────────────────

@router.post("/approvals/{approval_id}/explain")
async def explain_approval(approval_id: str, db: Session = Depends(get_db), _authz=require_permission("copilot:use")):
    """Explain an approval decision with anomaly detection and historical comparison."""
    from copilot_engine.assistants.approval_assistant import ApprovalAssistant
    assistant = ApprovalAssistant(db, _get_provider())
    result = await assistant.explain(approval_id)
    return result.to_dict()


# ── Solution Architecture ─────────────────────────────────────────────────────

@router.post("/solutions/suggest")
async def suggest_solution(req: SolutionSuggestRequest, db: Session = Depends(get_db), _authz=require_permission("copilot:use")):
    """Suggest solution architecture approaches grounded in historical patterns."""
    from copilot_engine.retrieval.context_retriever import ContextRetriever
    from copilot_engine.orchestration.copilot_runner import CopilotRunner

    chunks = ContextRetriever(db).retrieve_for_solution(
        req.requirements, rfp_type=req.rfp_type, top_k=6
    )
    memory_context = ContextRetriever.format_as_context(chunks)

    runner = CopilotRunner(db, _get_provider())
    result = await runner.run(
        prompt_name="solution_architecture_v1",
        prompt_vars={
            "requirements": req.requirements[:2000],
            "memory_context": memory_context,
            "opportunity_context": req.opportunity_context or "No additional opportunity context provided.",
        },
        context_chunks=chunks,
        expected_json_fields=["recommended_approach", "key_components", "reusable_patterns", "gaps_to_discover", "risks"],
    )
    return result.to_dict()


# ── Operational endpoints ─────────────────────────────────────────────────────

@router.get("/prompts")
def list_prompts():
    """List all registered copilot prompt templates (for audit and transparency)."""
    return {
        "prompts": prompt_registry.list_all(),
        "total": prompt_registry.count(),
    }


@router.get("/status")
def copilot_status():
    """Copilot engine health: provider config, registered prompts, active sessions."""
    from copilot_engine.config import LLM_PROVIDER, CLAUDE_API_KEY, OPENAI_API_KEY
    provider_configured = bool(CLAUDE_API_KEY or OPENAI_API_KEY)
    return {
        "status": "ok",
        "provider": LLM_PROVIDER,
        "provider_configured": provider_configured,
        "registered_prompts": prompt_registry.count(),
        "active_sessions": session_store.count(),
    }
