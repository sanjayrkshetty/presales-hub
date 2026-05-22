"""
Workflow Bottleneck Predictor.

Identifies stages where multiple proposals are simultaneously stalled,
creating a queue that will cascade into downstream delays.

A bottleneck is declared when:
  - ≥ 2 proposals are in the same non-terminal stage AND
  - the average elapsed fraction of SLA for those proposals > 0.5

Severity:
  low    1 proposal, elapsed < 0.5 SLA
  medium 2+ proposals OR elapsed 0.5–0.79 SLA
  high   3+ proposals OR any proposal already breached
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ProposalStageSnapshot:
    proposal_id: str
    stage: str
    elapsed_hours: float
    sla_hours: int
    pending_approvals: int = 0

    @property
    def elapsed_ratio(self) -> float:
        return self.elapsed_hours / self.sla_hours if self.sla_hours > 0 else 1.0

    @property
    def breached(self) -> bool:
        return self.elapsed_hours > self.sla_hours


@dataclass
class BottleneckPrediction:
    stage: str
    severity: str                               # low/medium/high
    affected_proposals: list[str] = field(default_factory=list)
    affected_count: int = 0
    avg_elapsed_ratio: float = 0.0
    estimated_delay_hours: float = 0.0
    factors: list[str] = field(default_factory=list)
    captured_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "severity": self.severity,
            "affected_proposals": self.affected_proposals,
            "affected_count": self.affected_count,
            "avg_elapsed_ratio": round(self.avg_elapsed_ratio, 3),
            "estimated_delay_hours": round(self.estimated_delay_hours, 1),
            "factors": self.factors,
            "captured_at": self.captured_at,
        }


_TERMINAL_STAGES = {"closed_won", "closed_lost", "submission"}


def _severity(count: int, avg_ratio: float, any_breached: bool) -> str:
    if any_breached or count >= 3:
        return "high"
    if count >= 2 or avg_ratio >= 0.5:
        return "medium"
    return "low"


def detect_bottlenecks(
    snapshots: list[ProposalStageSnapshot],
) -> list[BottleneckPrediction]:
    """
    Given a list of ProposalStageSnapshot objects (one per active proposal),
    return a sorted list of BottleneckPrediction (highest severity first).

    No DB access — caller is responsible for providing current state.
    """
    by_stage: dict[str, list[ProposalStageSnapshot]] = {}
    for snap in snapshots:
        if snap.stage in _TERMINAL_STAGES:
            continue
        by_stage.setdefault(snap.stage, []).append(snap)

    predictions: list[BottleneckPrediction] = []
    for stage, stage_snaps in by_stage.items():
        count = len(stage_snaps)
        avg_ratio = sum(s.elapsed_ratio for s in stage_snaps) / count
        any_breached = any(s.breached for s in stage_snaps)
        total_pending = sum(s.pending_approvals for s in stage_snaps)

        # Only surface noteworthy stages
        if count < 2 and avg_ratio < 0.5 and not any_breached:
            continue

        severity = _severity(count, avg_ratio, any_breached)

        factors: list[str] = []
        if count >= 2:
            factors.append(f"{count} proposals simultaneously in {stage}")
        if avg_ratio >= 0.7:
            factors.append(f"Average {avg_ratio:.0%} of SLA consumed")
        if any_breached:
            factors.append("At least one proposal already breached SLA")
        if total_pending >= 3:
            factors.append(f"{total_pending} pending approvals across stage")

        # Estimated delay: avg remaining SLA hours weighted by count
        avg_sla = sum(s.sla_hours for s in stage_snaps) / count
        estimated_delay = avg_sla * (1 - avg_ratio) * (0.5 + count * 0.1)

        predictions.append(BottleneckPrediction(
            stage=stage,
            severity=severity,
            affected_proposals=[s.proposal_id for s in stage_snaps],
            affected_count=count,
            avg_elapsed_ratio=avg_ratio,
            estimated_delay_hours=estimated_delay,
            factors=factors,
        ))

    # Sort: high → medium → low, then by affected_count desc
    _order = {"high": 0, "medium": 1, "low": 2}
    predictions.sort(key=lambda p: (_order[p.severity], -p.affected_count))
    return predictions
