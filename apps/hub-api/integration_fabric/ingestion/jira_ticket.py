"""Jira ticket ingestion pipeline — inbound issues → internal task records."""
from __future__ import annotations

import uuid
from integration_fabric.ingestion.pipeline import IngestionPipeline


_STATUS_MAP = {
    "To Do": "pending", "In Progress": "in_progress", "In Review": "review",
    "Done": "completed", "Closed": "completed", "Resolved": "completed",
    "Open": "pending", "Reopened": "in_progress",
}

_PRIORITY_MAP = {
    "Blocker": "critical", "Critical": "critical", "Major": "high",
    "High": "high", "Medium": "medium", "Minor": "low", "Trivial": "low",
}


class JiraTicketPipeline(IngestionPipeline):
    PIPELINE_NAME = "jira_ticket"
    SUPPORTED_SOURCES = ["jira"]

    def validate(self, raw: dict) -> tuple[bool, list[str]]:
        errors = []
        if not isinstance(raw, dict):
            return False, ["Input must be a dict with 'issues' list"]
        if not raw.get("issues"):
            errors.append("Missing 'issues' list")
        return not errors, errors

    def extract(self, raw: dict) -> list[dict]:
        return [{
            "key": issue.get("key", ""),
            "id": issue.get("id", ""),
            "summary": issue.get("fields", {}).get("summary", ""),
            "description": issue.get("fields", {}).get("description", ""),
            "status": issue.get("fields", {}).get("status", {}).get("name", ""),
            "priority": issue.get("fields", {}).get("priority", {}).get("name", "Medium"),
            "assignee": (issue.get("fields", {}).get("assignee") or {}).get("emailAddress", ""),
            "reporter": (issue.get("fields", {}).get("reporter") or {}).get("emailAddress", ""),
            "labels": issue.get("fields", {}).get("labels", []),
            "created": issue.get("fields", {}).get("created", ""),
            "updated": issue.get("fields", {}).get("updated", ""),
        } for issue in raw.get("issues", [])]

    def normalize(self, records: list[dict]) -> list[dict]:
        return [{
            "type": "jira_ticket",
            "internal_id": str(uuid.uuid4()),
            "jira_key": r["key"],
            "title": r["summary"],
            "description": r.get("description", ""),
            "status": _STATUS_MAP.get(r["status"], "pending"),
            "priority": _PRIORITY_MAP.get(r["priority"], "medium"),
            "assignee_email": r["assignee"],
            "reporter_email": r["reporter"],
            "labels": r["labels"],
            "created_at": r["created"],
            "updated_at": r["updated"],
        } for r in records]

    def route(self, normalized: list[dict], db=None) -> list[str]:
        return [r["internal_id"] for r in normalized]
