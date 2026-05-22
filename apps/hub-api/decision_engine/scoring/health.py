"""
Proposal Health Scorer.

Deterministic multi-factor scoring (0–100) with optional LLM narrative enrichment.
The numeric score is always rule-based and reproducible.
LLM enrichment (explanation text) is an async opt-in — skipped when
ANTHROPIC_API_KEY is absent or the API times out.

Score breakdown (sums to 100):
  content_completeness   30 pts  — which sections are filled in proposal.content
  timeline_defined       15 pts  — deadline set, reasonable horizon
  staffing_complete      15 pts  — at least one SME assigned
  risk_coverage          10 pts  — risk/threat section present
  compliance_coverage    10 pts  — compliance section present
  approval_readiness     10 pts  — review chain initialized
  stage_progress         10 pts  — stage-appropriate baseline

Readiness classification:
  green  ≥ 80
  yellow 60–79
  orange 40–59
  red    < 40
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional

logger = logging.getLogger("decision_engine.scoring.health")

MODEL_VERSION = "v1"

# Sections tracked in proposal.content and their max contribution
_CONTENT_SECTIONS: list[tuple[str, int]] = [
    ("exec_summary",     7),
    ("scope",            6),
    ("technical_approach", 5),
    ("methodology",      4),
    ("timeline",         3),
    ("team",             2),
    ("pricing",          2),
    ("risk_matrix",      1),
]
_CONTENT_MAX = sum(w for _, w in _CONTENT_SECTIONS)  # 30

_STAGE_BASELINE: dict[str, int] = {
    "intake": 0,
    "qualification": 1,
    "sme_assignment": 2,
    "drafting": 4,
    "technical_review": 6,
    "security_review": 7,
    "delivery_review": 7,
    "finance_review": 8,
    "legal_review": 9,
    "approval": 9,
    "submission": 10,
    "closed_won": 10,
    "closed_lost": 0,
}


@dataclass
class ScoreBreakdown:
    content_completeness: int = 0   # 0–30
    timeline_defined: int = 0       # 0–15
    staffing_complete: int = 0      # 0–15
    risk_coverage: int = 0          # 0–10
    compliance_coverage: int = 0    # 0–10
    approval_readiness: int = 0     # 0–10
    stage_progress: int = 0         # 0–10

    def total(self) -> int:
        return (
            self.content_completeness
            + self.timeline_defined
            + self.staffing_complete
            + self.risk_coverage
            + self.compliance_coverage
            + self.approval_readiness
            + self.stage_progress
        )


@dataclass
class ProposalHealthScore:
    proposal_id: str
    overall_score: int
    breakdown: ScoreBreakdown
    risk_factors: list[str] = field(default_factory=list)
    missing_requirements: list[str] = field(default_factory=list)
    readiness_classification: str = "red"
    explanation: Optional[str] = None
    model_version: str = MODEL_VERSION
    scored_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "overall_score": self.overall_score,
            "readiness_classification": self.readiness_classification,
            "breakdown": {
                "content_completeness": self.breakdown.content_completeness,
                "timeline_defined": self.breakdown.timeline_defined,
                "staffing_complete": self.breakdown.staffing_complete,
                "risk_coverage": self.breakdown.risk_coverage,
                "compliance_coverage": self.breakdown.compliance_coverage,
                "approval_readiness": self.breakdown.approval_readiness,
                "stage_progress": self.breakdown.stage_progress,
            },
            "risk_factors": self.risk_factors,
            "missing_requirements": self.missing_requirements,
            "explanation": self.explanation,
            "model_version": self.model_version,
            "scored_at": self.scored_at,
        }


def _classify(score: int) -> str:
    if score >= 80:
        return "green"
    if score >= 60:
        return "yellow"
    if score >= 40:
        return "orange"
    return "red"


def _score_content(content: dict) -> tuple[int, list[str]]:
    """Score section completeness; return (pts, missing_sections)."""
    raw = 0
    missing = []
    for key, weight in _CONTENT_SECTIONS:
        val = content.get(key)
        if val and str(val).strip():
            raw += weight
        else:
            missing.append(key.replace("_", " "))
    # Normalize to 30
    pts = round(raw / _CONTENT_MAX * 30)
    return pts, missing


def _score_timeline(deadline: Optional[date]) -> tuple[int, list[str]]:
    missing = []
    if not deadline:
        missing.append("proposal deadline")
        return 0, missing
    today = datetime.utcnow().date()
    delta = (deadline - today).days
    if delta < 0:
        return 5, ["deadline already passed"]
    if delta <= 7:
        return 8, []
    if delta <= 30:
        return 12, []
    return 15, []


def _score_staffing(assignments: list) -> tuple[int, list[str]]:
    if not assignments:
        return 0, ["no SME assigned"]
    active = [a for a in assignments if getattr(a, "status", "pending") != "completed"]
    if not active:
        return 8, ["all assignments completed — may need refresh"]
    return 15, []


def _score_approvals(approvals: list, stage: str) -> tuple[int, list[str]]:
    if not approvals:
        if stage in {"drafting", "technical_review", "security_review",
                     "delivery_review", "finance_review", "legal_review", "approval"}:
            return 0, ["approval chain not initialized"]
        return 10, []
    pending = [a for a in approvals if getattr(a, "status", "pending") == "pending"]
    if len(pending) == len(approvals):
        return 5, []
    return 10, []


def compute_health_score(
    proposal_id: str,
    stage: str,
    content: dict,
    assignments: list,
    approvals: list,
    deadline: Optional[date],
) -> ProposalHealthScore:
    """
    Pure deterministic health score computation.
    No I/O — all data must be passed in.
    """
    bd = ScoreBreakdown()

    # Content completeness (0–30)
    bd.content_completeness, missing_sections = _score_content(content)

    # Timeline (0–15)
    bd.timeline_defined, missing_timeline = _score_timeline(deadline)

    # Staffing (0–15)
    bd.staffing_complete, missing_staffing = _score_staffing(assignments)

    # Risk coverage (0–10)
    has_risk = bool(content.get("risk_matrix") or content.get("risks") or content.get("risk"))
    bd.risk_coverage = 10 if has_risk else 0

    # Compliance coverage (0–10)
    has_compliance = bool(
        content.get("compliance") or content.get("regulatory") or content.get("certifications")
    )
    bd.compliance_coverage = 10 if has_compliance else 0

    # Approval readiness (0–10)
    bd.approval_readiness, missing_approvals = _score_approvals(approvals, stage)

    # Stage progress bonus (0–10)
    bd.stage_progress = _STAGE_BASELINE.get(stage, 0)

    score = min(100, bd.total())

    # Risk factors
    risk_factors: list[str] = []
    if bd.content_completeness < 15:
        risk_factors.append("Proposal content critically incomplete")
    if bd.timeline_defined == 0:
        risk_factors.append("No deadline defined — deal velocity unknown")
    if bd.staffing_complete == 0:
        risk_factors.append("No SME assigned — execution risk")
    if bd.risk_coverage == 0 and stage not in {"intake", "qualification"}:
        risk_factors.append("Risk matrix absent")
    if bd.compliance_coverage == 0 and stage in {
        "security_review", "finance_review", "legal_review", "approval"
    }:
        risk_factors.append("Compliance section missing at late stage")

    missing_requirements = missing_sections + missing_timeline + missing_staffing + missing_approvals

    return ProposalHealthScore(
        proposal_id=proposal_id,
        overall_score=score,
        breakdown=bd,
        risk_factors=risk_factors,
        missing_requirements=missing_requirements,
        readiness_classification=_classify(score),
    )


async def enrich_with_llm(health: ProposalHealthScore, content: dict) -> ProposalHealthScore:
    """
    Optionally enrich a ProposalHealthScore with an LLM-generated narrative.
    Returns the same object with .explanation populated (or unchanged on failure).
    """
    try:
        from decision_engine.prompts.health_analysis import build_health_narrative
        explanation = await build_health_narrative(health, content)
        health.explanation = explanation
    except Exception as exc:
        logger.debug("LLM enrichment skipped: %s", exc)
    return health
