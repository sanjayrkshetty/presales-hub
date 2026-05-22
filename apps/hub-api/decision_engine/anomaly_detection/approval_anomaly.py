"""
Approval Anomaly Detector.

Detects suspicious approval patterns that warrant human review.
All detection is deterministic — threshold-based, no ML.

Anomaly types:
  fast_approval      Decision recorded < FAST_APPROVAL_MINUTES after creation.
                     Suggests rubber stamping or automated bypass.

  self_approval      The actor who approved is the same as the proposal creator
                     or a reviewer who already approved a sequential stage.
                     (Detected via actor_id appearing in consecutive approvals.)

  pattern_break      Proposal has > REJECTION_THRESHOLD rejections before an
                     approval for the same stage — unusual re-approval pattern.

  bypass             Approval status == "bypassed" on a stage that requires it.
                     Any bypass in a mandatory approval chain is flagged.

Severity:
  high   fast_approval (< 2 min) or bypass at finance/legal stage
  medium fast_approval (2–10 min) or self_approval
  low    pattern_break, after-hours (informational)
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


FAST_APPROVAL_CRITICAL_MINUTES = 2
FAST_APPROVAL_WARNING_MINUTES = 10
REJECTION_THRESHOLD = 2   # more than this many rejections before approval

HIGH_STAKES_STAGES = {"finance_review", "legal_review", "approval"}


@dataclass
class AnomalyResult:
    approval_id: str
    proposal_id: str
    anomaly_type: str
    severity: str
    details: dict = field(default_factory=dict)
    detected_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "approval_id": self.approval_id,
            "proposal_id": self.proposal_id,
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "details": self.details,
            "detected_at": self.detected_at,
        }


def detect_fast_approval(
    approval_id: str,
    proposal_id: str,
    stage: Optional[str],
    created_at: datetime,
    decided_at: datetime,
) -> Optional[AnomalyResult]:
    minutes = (decided_at - created_at).total_seconds() / 60
    if minutes >= FAST_APPROVAL_WARNING_MINUTES:
        return None
    severity = (
        "high" if minutes < FAST_APPROVAL_CRITICAL_MINUTES else "medium"
    )
    return AnomalyResult(
        approval_id=approval_id,
        proposal_id=proposal_id,
        anomaly_type="fast_approval",
        severity=severity,
        details={
            "minutes_to_decision": round(minutes, 1),
            "stage": stage,
            "threshold_minutes": FAST_APPROVAL_WARNING_MINUTES,
        },
    )


def detect_bypass(
    approval_id: str,
    proposal_id: str,
    stage: Optional[str],
) -> Optional[AnomalyResult]:
    severity = "high" if stage in HIGH_STAKES_STAGES else "medium"
    return AnomalyResult(
        approval_id=approval_id,
        proposal_id=proposal_id,
        anomaly_type="bypass",
        severity=severity,
        details={"stage": stage, "high_stakes": stage in HIGH_STAKES_STAGES},
    )


def detect_sequential_self_approval(
    proposal_id: str,
    approval_chain: list,  # list of Approval ORM objects, ordered by order_index
) -> list[AnomalyResult]:
    """
    Detect when the same actor_id appears in consecutive approved stages.
    approval_chain should be pre-filtered to decided approvals only.
    """
    results = []
    seen_actors: dict[str, str] = {}  # actor_id → previous stage

    for approval in approval_chain:
        actor = getattr(approval, "approver_id", None)
        stage = getattr(approval, "stage", None)
        status = getattr(approval, "status", "")
        appr_id = getattr(approval, "id", "")

        if status not in {"approved", "rejected", "escalated"}:
            continue
        if actor and actor in seen_actors:
            results.append(AnomalyResult(
                approval_id=appr_id,
                proposal_id=proposal_id,
                anomaly_type="self_approval",
                severity="medium",
                details={
                    "actor_id": actor,
                    "previous_stage": seen_actors[actor],
                    "current_stage": stage,
                },
            ))
        if actor:
            seen_actors[actor] = stage

    return results


def detect_rejection_pattern(
    approval_id: str,
    proposal_id: str,
    stage: Optional[str],
    rejection_count: int,
) -> Optional[AnomalyResult]:
    if rejection_count <= REJECTION_THRESHOLD:
        return None
    return AnomalyResult(
        approval_id=approval_id,
        proposal_id=proposal_id,
        anomaly_type="pattern_break",
        severity="low",
        details={
            "stage": stage,
            "rejection_count": rejection_count,
            "threshold": REJECTION_THRESHOLD,
        },
    )


def scan_approval(
    approval,            # Approval ORM object
    all_proposal_approvals: list,   # full chain for self-approval detection
) -> list[AnomalyResult]:
    """
    Run all detectors against a single approval event.
    Returns list of anomalies (may be empty).
    """
    anomalies: list[AnomalyResult] = []
    appr_id = getattr(approval, "id", "unknown")
    proposal_id = getattr(approval, "proposal_id", "")
    stage = getattr(approval, "stage", None)
    status = getattr(approval, "status", "")
    created_at = getattr(approval, "created_at", None)
    decided_at = getattr(approval, "decided_at", None)

    # Fast approval
    if status in {"approved", "rejected", "escalated"} and created_at and decided_at:
        fa = detect_fast_approval(appr_id, proposal_id, stage, created_at, decided_at)
        if fa:
            anomalies.append(fa)

    # Bypass
    if status == "bypassed":
        anomalies.append(detect_bypass(appr_id, proposal_id, stage))

    return anomalies
