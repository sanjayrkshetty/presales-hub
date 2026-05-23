"""Escalation → Microsoft Teams notification sync."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class TeamsSyncResult:
    notifications_sent: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def push_escalations_to_teams(
    db: "Session",
    teams_connector,
    team_id: str,
    channel_id: str,
    min_risk: str = "high",
    dry_run: bool = False,
) -> TeamsSyncResult:
    from strategic_intelligence.prediction.escalation_predictor import predict_escalations

    result = TeamsSyncResult()
    valid_levels = ["low", "medium", "high", "critical"]
    min_idx = valid_levels.index(min_risk) if min_risk in valid_levels else 2

    report = predict_escalations(db)
    high_signals = [s for s in report.signals if valid_levels.index(s.risk_level) >= min_idx]

    for signal in high_signals:
        text = (
            f"🚨 **Escalation Alert** — Risk: {signal.risk_level.upper()}\n"
            f"Proposal: `{signal.proposal_id[:8]}`\n"
            f"Score: {signal.score:.2f}\n"
            f"Action: {signal.recommended_action}\n"
            f"Rationale: {signal.rationale}"
        )
        if not dry_run:
            push = teams_connector.send_notification(team_id=team_id, channel_id=channel_id, text=text)
            if push.success:
                result.notifications_sent += 1
            else:
                result.errors.append(f"Teams send failed: {push.error}")
        else:
            result.notifications_sent += 1

    return result
