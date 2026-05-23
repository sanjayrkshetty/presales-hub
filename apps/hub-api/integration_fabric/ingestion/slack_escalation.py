"""Slack escalation message ingestion pipeline."""
from __future__ import annotations

import re
import uuid
from integration_fabric.ingestion.pipeline import IngestionPipeline

_URGENCY_KEYWORDS = {
    "critical": ["critical", "down", "outage", "breach", "sla breach", "escalate immediately"],
    "high": ["urgent", "asap", "blocker", "blocked", "escalate", "overdue"],
    "medium": ["help", "issue", "problem", "delay", "stuck"],
    "low": ["fyi", "heads up", "note", "reminder"],
}


def _detect_urgency(text: str) -> str:
    lower = text.lower()
    for level, kws in _URGENCY_KEYWORDS.items():
        if any(kw in lower for kw in kws):
            return level
    return "low"


def _extract_mentions(text: str) -> list[str]:
    return re.findall(r"<@([A-Z0-9]+)>", text)


def _extract_proposal_refs(text: str) -> list[str]:
    return re.findall(r"(?:proposal|prop|rfp)[:\s#-]*([A-Za-z0-9-]{8,36})", text, re.IGNORECASE)


class SlackEscalationPipeline(IngestionPipeline):
    PIPELINE_NAME = "slack_escalation"
    SUPPORTED_SOURCES = ["slack"]

    def validate(self, raw: dict) -> tuple[bool, list[str]]:
        errors = []
        if not isinstance(raw, dict):
            return False, ["Input must be a dict"]
        if not raw.get("text"):
            errors.append("Missing 'text'")
        if not raw.get("channel"):
            errors.append("Missing 'channel'")
        return not errors, errors

    def extract(self, raw: dict) -> list[dict]:
        return [{
            "ts": raw.get("ts", ""),
            "channel": raw.get("channel", ""),
            "user": raw.get("user", ""),
            "text": raw.get("text", ""),
            "thread_ts": raw.get("thread_ts"),
            "attachments": raw.get("attachments", []),
        }]

    def normalize(self, records: list[dict]) -> list[dict]:
        return [{
            "type": "slack_escalation",
            "internal_id": str(uuid.uuid4()),
            "ts": r["ts"],
            "channel": r["channel"],
            "user_id": r["user"],
            "text": r["text"],
            "urgency": _detect_urgency(r["text"]),
            "mentions": _extract_mentions(r["text"]),
            "proposal_refs": _extract_proposal_refs(r["text"]),
            "thread_ts": r.get("thread_ts"),
        } for r in records]

    def route(self, normalized: list[dict], db=None) -> list[str]:
        return [r["internal_id"] for r in normalized]
