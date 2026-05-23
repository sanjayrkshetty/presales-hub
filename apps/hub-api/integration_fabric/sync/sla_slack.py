"""SLA breach → Slack alert sync."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class SlackSyncResult:
    alerts_sent: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def push_sla_breaches_to_slack(
    db: "Session",
    slack_connector,
    channel: str,
    dry_run: bool = False,
) -> SlackSyncResult:
    from sqlalchemy import select
    from datetime import date
    from models import Proposal

    result = SlackSyncResult()
    proposals = db.scalars(select(Proposal)).all()

    overdue = [
        p for p in proposals
        if p.stage not in ("closed_won", "closed_lost")
        and hasattr(p, "opportunity") and p.opportunity
        and getattr(p.opportunity, "deadline", None)
        and p.opportunity.deadline < date.today()
    ]

    for p in overdue:
        opp = getattr(p, "opportunity", None)
        deadline = opp.deadline if opp else "unknown"
        text = (
            f":rotating_light: *SLA Breach Detected*\n"
            f"Proposal `{p.id[:8]}` — Stage: `{p.stage}`\n"
            f"Deadline: {deadline} (overdue)\n"
            f"Immediate review required."
        )
        if not dry_run:
            push = slack_connector.send_alert(channel=channel, text=text)
            if push.success:
                result.alerts_sent += 1
            else:
                result.errors.append(f"Failed to send alert for {p.id}: {push.error}")
        else:
            result.alerts_sent += 1

    return result
