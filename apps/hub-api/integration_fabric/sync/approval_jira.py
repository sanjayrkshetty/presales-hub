"""Approval status ↔ Jira workflow update sync."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_APPROVAL_TO_JIRA_TRANSITION = {
    "pending": "In Progress",
    "approved": "Done",
    "rejected": "Closed",
}


@dataclass
class JiraSyncResult:
    transitions_pushed: int = 0
    issues_created: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def sync_approvals_to_jira(
    db: "Session",
    jira_connector,
    project_key: str = "PRESALES",
    dry_run: bool = False,
) -> JiraSyncResult:
    from sqlalchemy import select
    from models import Approval

    result = JiraSyncResult()
    approvals = db.scalars(select(Approval)).all()

    for appr in approvals:
        jira_status = _APPROVAL_TO_JIRA_TRANSITION.get(appr.status, "In Progress")
        transition_record = {
            "issue_id": f"{project_key}-{appr.id[:6].upper()}",
            "transition": jira_status,
            "approval_id": appr.id,
            "stage": appr.stage,
        }
        if not dry_run:
            push = jira_connector.push("transition", [transition_record])
            if push.success:
                result.transitions_pushed += 1
            else:
                result.errors.append(f"Failed transition for {appr.id}: {push.error}")
        else:
            result.transitions_pushed += 1

    return result
