"""
Deal Risk Scorer.

Combines opportunity-level signals into a single risk score + risk_level.
Deterministic — no LLM dependency.

Factors (sums to 100):
  deadline_pressure   30 pts  — proximity to deadline
  win_probability     25 pts  — inverse: low win prob → high risk
  value_exposure      20 pts  — large deals = higher risk
  stage_alignment     15 pts  — is stage appropriate for timeline?
  approval_velocity   10 pts  — stalled approvals = risk signal

Risk levels: low (<30) / medium (30–54) / high (55–74) / critical (≥75)
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional


@dataclass
class DealRiskScore:
    opportunity_id: str
    risk_score: int                         # 0–100 (higher = riskier)
    risk_level: str                         # low/medium/high/critical
    factors: list[dict] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    scored_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "opportunity_id": self.opportunity_id,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "factors": self.factors,
            "recommendations": self.recommendations,
            "scored_at": self.scored_at,
        }


def _classify_risk(score: int) -> str:
    if score >= 75:
        return "critical"
    if score >= 55:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def _deadline_pressure(deadline: Optional[date]) -> tuple[int, str]:
    if not deadline:
        return 20, "No deadline set — planning risk"
    today = datetime.utcnow().date()
    days = (deadline - today).days
    if days < 0:
        return 30, f"Deadline overdue by {abs(days)} days"
    if days <= 7:
        return 28, f"Deadline in {days} days — critical"
    if days <= 21:
        return 20, f"Deadline in {days} days — tight"
    if days <= 60:
        return 10, f"Deadline in {days} days — manageable"
    return 5, f"Deadline in {days} days — comfortable"


def _win_probability_risk(win_pct: int) -> tuple[int, str]:
    # Low win probability → high risk
    if win_pct <= 20:
        return 25, f"Win probability critically low at {win_pct}%"
    if win_pct <= 40:
        return 18, f"Win probability low at {win_pct}%"
    if win_pct <= 60:
        return 10, f"Win probability moderate at {win_pct}%"
    return 3, f"Win probability healthy at {win_pct}%"


def _value_exposure(deal_value_cr: Optional[float]) -> tuple[int, str]:
    if not deal_value_cr:
        return 5, "Deal value undefined"
    if deal_value_cr >= 20:
        return 20, f"High-value deal (₹{deal_value_cr:.1f} Cr) — execution risk elevated"
    if deal_value_cr >= 10:
        return 12, f"Mid-tier deal (₹{deal_value_cr:.1f} Cr)"
    return 5, f"Standard deal value (₹{deal_value_cr:.1f} Cr)"


_LATE_STAGES = {"technical_review", "security_review", "delivery_review",
                "finance_review", "legal_review", "approval", "submission"}
_EXPECTED_DAYS: dict[str, int] = {
    "intake": 3, "qualification": 7, "sme_assignment": 2,
    "drafting": 14, "technical_review": 5, "security_review": 5,
    "delivery_review": 5, "finance_review": 4, "legal_review": 5,
    "approval": 2, "submission": 1,
}


def _stage_alignment(stage: str, deadline: Optional[date], created_at: Optional[datetime]) -> tuple[int, str]:
    if not deadline or not created_at:
        return 8, "Cannot assess stage alignment — missing dates"
    today = datetime.utcnow().date()
    total_days = max(1, (deadline - created_at.date()).days)
    elapsed_days = (today - created_at.date()).days
    elapsed_ratio = elapsed_days / total_days

    # Estimate expected progress ratio from stage ordering
    stage_order = list(_EXPECTED_DAYS.keys())
    try:
        idx = stage_order.index(stage)
        expected_ratio = sum(list(_EXPECTED_DAYS.values())[:idx]) / max(1, sum(_EXPECTED_DAYS.values()))
    except ValueError:
        expected_ratio = 0.5

    lag = elapsed_ratio - expected_ratio
    if lag > 0.3:
        return 15, f"Proposal is significantly behind expected pace (lag {lag:.0%})"
    if lag > 0.1:
        return 8, f"Proposal slightly behind pace (lag {lag:.0%})"
    return 3, "Stage progression on track"


def _approval_velocity(pending_approvals: int, total_approvals: int) -> tuple[int, str]:
    if total_approvals == 0:
        return 5, "No approval chain initialized"
    pct_pending = pending_approvals / total_approvals
    if pct_pending >= 0.8:
        return 10, f"{pending_approvals}/{total_approvals} approvals still pending"
    if pct_pending >= 0.5:
        return 6, f"{pending_approvals}/{total_approvals} approvals pending"
    return 2, "Approval chain progressing well"


def compute_deal_risk(
    opportunity_id: str,
    stage: str,
    win_probability: int,
    deal_value_cr: Optional[float],
    deadline: Optional[date],
    created_at: Optional[datetime],
    pending_approvals: int,
    total_approvals: int,
) -> DealRiskScore:
    factors = []
    recs = []

    dp_pts, dp_label = _deadline_pressure(deadline)
    factors.append({"factor": "deadline_pressure", "score": dp_pts, "detail": dp_label})
    if dp_pts >= 20:
        recs.append("Escalate deadline risk to presales lead immediately")

    wp_pts, wp_label = _win_probability_risk(win_probability)
    factors.append({"factor": "win_probability", "score": wp_pts, "detail": wp_label})
    if wp_pts >= 18:
        recs.append("Schedule qualification review — low win probability")

    ve_pts, ve_label = _value_exposure(deal_value_cr)
    factors.append({"factor": "value_exposure", "score": ve_pts, "detail": ve_label})
    if ve_pts >= 12:
        recs.append("Assign senior solution architect for high-value deal")

    sa_pts, sa_label = _stage_alignment(stage, deadline, created_at)
    factors.append({"factor": "stage_alignment", "score": sa_pts, "detail": sa_label})
    if sa_pts >= 10:
        recs.append("Accelerate stage progression — proposal pace lagging")

    av_pts, av_label = _approval_velocity(pending_approvals, total_approvals)
    factors.append({"factor": "approval_velocity", "score": av_pts, "detail": av_label})
    if av_pts >= 8:
        recs.append("Nudge reviewers — approval chain stalled")

    risk_score = min(100, dp_pts + wp_pts + ve_pts + sa_pts + av_pts)
    return DealRiskScore(
        opportunity_id=opportunity_id,
        risk_score=risk_score,
        risk_level=_classify_risk(risk_score),
        factors=factors,
        recommendations=recs,
    )
