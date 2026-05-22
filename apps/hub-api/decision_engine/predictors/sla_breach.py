"""
SLA Breach Predictor.

Estimates the probability that a proposal will breach its stage SLA before
an approver or SME acts.  Fully deterministic — no randomness.

Probability model:
  base       = elapsed_ratio² (exponential — slow growth until ~75% elapsed,
                then accelerates sharply)
  + approval_penalty  = min(pending_approvals * 0.12, 0.30)
  + workload_penalty  = min(sme_workload / 4 * 0.20, 0.20)
  clamped to [0.0, 1.0]

Risk levels:
  low      < 0.20
  medium   0.20 – 0.49
  high     0.50 – 0.79
  critical ≥ 0.80
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class BreachRiskScore:
    proposal_id: str
    stage: str
    breach_probability: float               # 0.0 – 1.0
    predicted_hours_to_breach: Optional[float]
    risk_level: str                         # low/medium/high/critical
    elapsed_hours: float
    sla_hours: int
    factors: list[dict] = field(default_factory=list)
    predicted_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "stage": self.stage,
            "breach_probability": round(self.breach_probability, 3),
            "predicted_hours_to_breach": (
                round(self.predicted_hours_to_breach, 1)
                if self.predicted_hours_to_breach is not None else None
            ),
            "risk_level": self.risk_level,
            "elapsed_hours": round(self.elapsed_hours, 1),
            "sla_hours": self.sla_hours,
            "factors": self.factors,
            "predicted_at": self.predicted_at,
        }


def _classify_risk(prob: float) -> str:
    if prob >= 0.80:
        return "critical"
    if prob >= 0.50:
        return "high"
    if prob >= 0.20:
        return "medium"
    return "low"


def predict_breach(
    proposal_id: str,
    stage: str,
    stage_entered_at: datetime,
    sla_hours: int,
    pending_approvals: int = 0,
    sme_workload: int = 0,
    now: Optional[datetime] = None,
) -> BreachRiskScore:
    """
    All inputs must be provided by the caller — no DB access here.

    stage_entered_at: when the proposal entered the current stage (UTC).
    sla_hours:        SLA budget for this stage.
    pending_approvals: count of pending approvals at this stage.
    sme_workload:     current_workload of the assigned SME (0–4+).
    """
    if now is None:
        now = datetime.utcnow()

    elapsed_seconds = max(0.0, (now - stage_entered_at).total_seconds())
    elapsed_hours = elapsed_seconds / 3600.0
    remaining_hours = max(0.0, sla_hours - elapsed_hours)

    if sla_hours <= 0:
        elapsed_ratio = 1.0
    else:
        elapsed_ratio = min(1.0, elapsed_hours / sla_hours)

    # Already breached
    if elapsed_hours > sla_hours:
        factors = [
            {"factor": "already_breached", "detail": f"Elapsed {elapsed_hours:.1f}h > SLA {sla_hours}h"},
        ]
        return BreachRiskScore(
            proposal_id=proposal_id,
            stage=stage,
            breach_probability=1.0,
            predicted_hours_to_breach=0.0,
            risk_level="critical",
            elapsed_hours=elapsed_hours,
            sla_hours=sla_hours,
            factors=factors,
        )

    # Base probability from time consumed (quadratic)
    base = elapsed_ratio ** 2
    approval_penalty = min(pending_approvals * 0.12, 0.30)
    workload_penalty = min((sme_workload / 4.0) * 0.20, 0.20)
    probability = min(1.0, base + approval_penalty + workload_penalty)

    factors = [
        {
            "factor": "time_elapsed",
            "detail": f"{elapsed_hours:.1f}h of {sla_hours}h used ({elapsed_ratio:.0%})",
            "contribution": round(base, 3),
        },
    ]
    if pending_approvals:
        factors.append({
            "factor": "pending_approvals",
            "detail": f"{pending_approvals} approvals waiting",
            "contribution": round(approval_penalty, 3),
        })
    if sme_workload > 2:
        factors.append({
            "factor": "sme_overload",
            "detail": f"SME workload at {sme_workload}/4",
            "contribution": round(workload_penalty, 3),
        })

    # Projected hours until breach (linear extrapolation from current rate)
    predicted_hours = remaining_hours if elapsed_hours > 0 else float(sla_hours)

    return BreachRiskScore(
        proposal_id=proposal_id,
        stage=stage,
        breach_probability=probability,
        predicted_hours_to_breach=predicted_hours,
        risk_level=_classify_risk(probability),
        elapsed_hours=elapsed_hours,
        sla_hours=sla_hours,
        factors=factors,
    )
