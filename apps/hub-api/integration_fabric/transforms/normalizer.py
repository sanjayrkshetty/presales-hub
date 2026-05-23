"""
Data normalizer — maps platform-specific field names to platform-agnostic schema.

Platform-agnostic schema for opportunities:
  id, title, value_cr, stage, client, deadline, source, raw

For proposals:
  id, title, stage, opportunity_id, source, raw
"""
from __future__ import annotations

from typing import Any


_STAGE_CANON = {
    # Salesforce
    "Prospecting": "intake", "Qualification": "qualification",
    "Proposal/Price Quote": "proposal_review", "Negotiation/Review": "approval",
    "Closed Won": "closed_won", "Closed Lost": "closed_lost",
    # HubSpot
    "appointmentscheduled": "intake", "qualifiedtobuy": "qualification",
    "contractsent": "approval", "closedwon": "closed_won", "closedlost": "closed_lost",
    # Internal
    "intake": "intake", "qualification": "qualification", "proposal_review": "proposal_review",
    "technical_review": "technical_review", "security_review": "security_review",
    "approval": "approval", "closed_won": "closed_won", "closed_lost": "closed_lost",
}


def normalize_opportunity(record: dict, source: str) -> dict:
    if source == "salesforce":
        return {
            "id": record.get("Id", ""),
            "title": record.get("Name", ""),
            "value_cr": _amount_to_cr(record.get("Amount")),
            "stage": _STAGE_CANON.get(record.get("StageName", ""), "intake"),
            "client": record.get("Account", {}).get("Name", "") if isinstance(record.get("Account"), dict) else "",
            "deadline": record.get("CloseDate", ""),
            "source": "salesforce",
            "raw": record,
        }
    if source == "hubspot":
        props = record.get("properties", {})
        return {
            "id": record.get("id", ""),
            "title": props.get("dealname", ""),
            "value_cr": _amount_to_cr(props.get("amount")),
            "stage": _STAGE_CANON.get(props.get("dealstage", ""), "intake"),
            "client": "",
            "deadline": props.get("closedate", ""),
            "source": "hubspot",
            "raw": record,
        }
    return {"id": record.get("id", ""), "source": source, "raw": record}


def normalize_issue(record: dict, source: str) -> dict:
    if source == "jira":
        fields = record.get("fields", {})
        return {
            "id": record.get("key", ""),
            "title": fields.get("summary", ""),
            "status": fields.get("status", {}).get("name", "") if isinstance(fields.get("status"), dict) else "",
            "priority": fields.get("priority", {}).get("name", "Medium") if isinstance(fields.get("priority"), dict) else "Medium",
            "assignee": (fields.get("assignee") or {}).get("emailAddress", ""),
            "source": "jira",
            "raw": record,
        }
    if source == "servicenow":
        return {
            "id": record.get("number", ""),
            "title": record.get("short_description", ""),
            "status": record.get("state", ""),
            "priority": record.get("priority", ""),
            "assignee": record.get("assigned_to", ""),
            "source": "servicenow",
            "raw": record,
        }
    return {"id": record.get("id", ""), "source": source, "raw": record}


def _amount_to_cr(amount: Any) -> float:
    try:
        return round(float(amount or 0) / 1_000_000, 3)
    except (TypeError, ValueError):
        return 0.0
