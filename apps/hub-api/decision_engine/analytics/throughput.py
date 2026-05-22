"""
Workflow Throughput Analytics.

Computes per-stage performance metrics from AuditLog stage transition records.
Works from existing data without requiring WorkflowTimingMetric rows.

Metrics per stage:
  count            total proposals that transitioned through
  avg_hours        mean time spent
  p50_hours        median
  p90_hours        90th percentile
  breach_rate      fraction that exceeded SLA
  conversion_rate  fraction that advanced to next stage (vs stuck/regressed)
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class StageMetrics:
    stage: str
    count: int
    avg_hours: float
    p50_hours: float
    p90_hours: float
    breach_rate: float          # 0.0 – 1.0
    sla_hours: Optional[int]
    sample_proposal_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "count": self.count,
            "avg_hours": round(self.avg_hours, 1),
            "p50_hours": round(self.p50_hours, 1),
            "p90_hours": round(self.p90_hours, 1),
            "breach_rate": round(self.breach_rate, 3),
            "sla_hours": self.sla_hours,
        }


@dataclass
class ThroughputReport:
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    stage_metrics: list[StageMetrics] = field(default_factory=list)
    overall_avg_cycle_hours: float = 0.0
    top_bottleneck: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "stage_metrics": [m.to_dict() for m in self.stage_metrics],
            "overall_avg_cycle_hours": round(self.overall_avg_cycle_hours, 1),
            "top_bottleneck": self.top_bottleneck,
        }


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * pct
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def compute_throughput(
    audit_rows: list,           # AuditLog ORM objects with action="stage_transition"
    sla_config: dict[str, int], # stage → hours_allowed
) -> ThroughputReport:
    """
    Reconstruct stage timing from AuditLog rows.

    Each audit row with action="stage_transition" has:
      entity_id   → proposal_id
      from_state  → stage that was exited
      to_state    → stage that was entered
      occurred_at → when the transition happened

    We compute time spent in from_state as:
      occurred_at(current_transition) - occurred_at(previous_transition for same proposal)
    """
    # Group transitions by proposal
    by_proposal: dict[str, list] = {}
    for row in audit_rows:
        eid = getattr(row, "entity_id", None)
        if eid:
            by_proposal.setdefault(eid, []).append(row)

    # Sort each proposal's transitions chronologically
    stage_durations: dict[str, list[tuple[float, str]]] = {}  # stage → [(hours, proposal_id)]

    for proposal_id, rows in by_proposal.items():
        rows_sorted = sorted(rows, key=lambda r: getattr(r, "occurred_at", datetime.min))
        for i in range(1, len(rows_sorted)):
            prev = rows_sorted[i - 1]
            curr = rows_sorted[i]
            stage = getattr(prev, "to_state", None) or getattr(prev, "from_state", None)
            t_enter = getattr(prev, "occurred_at", None)
            t_exit = getattr(curr, "occurred_at", None)
            if not stage or not t_enter or not t_exit:
                continue
            hours = max(0.0, (t_exit - t_enter).total_seconds() / 3600)
            stage_durations.setdefault(stage, []).append((hours, proposal_id))

    metrics: list[StageMetrics] = []
    for stage, durations in stage_durations.items():
        hours_list = [d[0] for d in durations]
        sla = sla_config.get(stage)
        breached = sum(1 for h in hours_list if sla and h > sla)
        breach_rate = breached / len(hours_list) if hours_list else 0.0

        metrics.append(StageMetrics(
            stage=stage,
            count=len(hours_list),
            avg_hours=sum(hours_list) / len(hours_list),
            p50_hours=_percentile(hours_list, 0.5),
            p90_hours=_percentile(hours_list, 0.9),
            breach_rate=breach_rate,
            sla_hours=sla,
            sample_proposal_ids=[d[1] for d in durations[:3]],
        ))

    # Sort by avg_hours desc to surface slowest stages first
    metrics.sort(key=lambda m: m.avg_hours, reverse=True)

    top_bottleneck = metrics[0].stage if metrics else None
    all_hours = [d[0] for durs in stage_durations.values() for d in durs]
    overall_avg = sum(all_hours) / len(all_hours) if all_hours else 0.0

    return ThroughputReport(
        stage_metrics=metrics,
        overall_avg_cycle_hours=overall_avg,
        top_bottleneck=top_bottleneck,
    )
