"""
SME Recommendation Ranker.

Ranks candidate SMEs for a proposal using a composite score of:
  expertise_match    45%  — Jaccard similarity between SME expertise and required tags
  workload_score     30%  — inverse linear penalty on current_workload (max 4)
  historical_success 25%  — historical approval/success rate from AuditLog

Returns a ranked list of CandidateRanking with per-factor explanations.
The #1 candidate is the recommended assignment; human override is always available.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CandidateRanking:
    stakeholder_id: str
    name: str
    composite_score: float          # 0.0–1.0
    expertise_match: float
    workload_score: float
    historical_success: float
    current_workload: int
    matching_tags: list[str] = field(default_factory=list)
    missing_tags: list[str] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "stakeholder_id": self.stakeholder_id,
            "name": self.name,
            "composite_score": round(self.composite_score, 3),
            "expertise_match": round(self.expertise_match, 3),
            "workload_score": round(self.workload_score, 3),
            "historical_success": round(self.historical_success, 3),
            "current_workload": self.current_workload,
            "matching_tags": self.matching_tags,
            "missing_tags": self.missing_tags,
            "explanation": self.explanation,
        }


@dataclass
class SmeRankingResult:
    proposal_id: str
    rfp_type: Optional[str]
    required_expertise: list[str]
    ranked: list[CandidateRanking] = field(default_factory=list)
    recommended: Optional[CandidateRanking] = None
    ranked_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "rfp_type": self.rfp_type,
            "required_expertise": self.required_expertise,
            "recommended": self.recommended.to_dict() if self.recommended else None,
            "ranked": [c.to_dict() for c in self.ranked],
            "ranked_at": self.ranked_at,
        }


def _jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def _workload_score(workload: int, max_workload: int = 4) -> float:
    """Higher workload → lower score. At max_workload returns 0."""
    return max(0.0, 1.0 - workload / max_workload)


def _build_explanation(c: CandidateRanking, required: list[str]) -> str:
    parts = []
    pct = int(c.expertise_match * 100)
    parts.append(f"{pct}% expertise match")
    if c.matching_tags:
        parts.append(f"covers: {', '.join(c.matching_tags)}")
    if c.missing_tags:
        parts.append(f"gaps: {', '.join(c.missing_tags)}")
    cap = int(c.workload_score * 100)
    parts.append(f"{cap}% capacity available")
    hist = int(c.historical_success * 100)
    parts.append(f"{hist}% historical success rate")
    return ". ".join(parts) + "."


def rank_sme_candidates(
    proposal_id: str,
    rfp_type: Optional[str],
    required_expertise: list[str],
    candidates: list,               # list of Stakeholder ORM objects
    historical_success: dict[str, float],  # stakeholder_id → success rate (0–1)
) -> SmeRankingResult:
    """
    Pure ranking function — no DB access.

    candidates: Stakeholder ORM objects with .id, .name, .expertise (list), .current_workload
    historical_success: pre-computed from AuditLog by caller
    """
    required_set = {tag.lower().strip() for tag in required_expertise}
    ranked: list[CandidateRanking] = []

    for sme in candidates:
        sme_tags = {tag.lower().strip() for tag in (sme.expertise or [])}
        exp_match = _jaccard(required_set, sme_tags)
        wl_score = _workload_score(sme.current_workload)
        hist = historical_success.get(sme.id, 0.5)  # default 50% if no history

        composite = (exp_match * 0.45) + (wl_score * 0.30) + (hist * 0.25)

        matching = sorted(required_set & sme_tags)
        missing = sorted(required_set - sme_tags)

        cr = CandidateRanking(
            stakeholder_id=sme.id,
            name=sme.name,
            composite_score=composite,
            expertise_match=exp_match,
            workload_score=wl_score,
            historical_success=hist,
            current_workload=sme.current_workload,
            matching_tags=matching,
            missing_tags=missing,
        )
        cr.explanation = _build_explanation(cr, required_expertise)
        ranked.append(cr)

    ranked.sort(key=lambda c: c.composite_score, reverse=True)

    return SmeRankingResult(
        proposal_id=proposal_id,
        rfp_type=rfp_type,
        required_expertise=required_expertise,
        ranked=ranked,
        recommended=ranked[0] if ranked else None,
    )
