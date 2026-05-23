"""Meeting notes ingestion pipeline."""
from __future__ import annotations

import re
import uuid
from integration_fabric.ingestion.pipeline import IngestionPipeline


def _extract_action_items(text: str) -> list[dict]:
    patterns = [
        r"action item[:\s]+([^\n]{10,120})",
        r"(?:AI|todo|to-do)[:\s]+([^\n]{10,120})",
        r"(?:@\w+|assigned to \w+)[:\s]+([^\n]{10,120})",
    ]
    items = []
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            items.append({"text": m.group(1).strip(), "owner": None})
    return items[:20]


def _extract_decisions(text: str) -> list[str]:
    patterns = [r"(?:decided|agreed|resolved|decision)[:\s]+([^\n]{10,150})"]
    decisions = []
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            decisions.append(m.group(1).strip())
    return decisions[:10]


class MeetingNotesPipeline(IngestionPipeline):
    PIPELINE_NAME = "meeting_notes"
    SUPPORTED_SOURCES = ["manual", "teams", "outlook", "gdrive", "confluence"]

    def validate(self, raw: dict) -> tuple[bool, list[str]]:
        errors = []
        if not isinstance(raw, dict):
            return False, ["Input must be a dict"]
        if not raw.get("title"):
            errors.append("Missing 'title'")
        if not raw.get("content"):
            errors.append("Missing 'content'")
        return not errors, errors

    def extract(self, raw: dict) -> list[dict]:
        return [{
            "title": raw.get("title", ""),
            "content": raw.get("content", ""),
            "date": raw.get("date", ""),
            "attendees": raw.get("attendees", []),
            "source": raw.get("source", "manual"),
            "proposal_id": raw.get("proposal_id"),
            "opportunity_id": raw.get("opportunity_id"),
        }]

    def normalize(self, records: list[dict]) -> list[dict]:
        return [{
            "type": "meeting_notes",
            "internal_id": str(uuid.uuid4()),
            "title": r["title"],
            "date": r["date"],
            "attendees": r["attendees"],
            "content_preview": r["content"][:500],
            "action_items": _extract_action_items(r["content"]),
            "decisions": _extract_decisions(r["content"]),
            "source": r["source"],
            "proposal_id": r.get("proposal_id"),
            "opportunity_id": r.get("opportunity_id"),
        } for r in records]

    def route(self, normalized: list[dict], db=None) -> list[str]:
        return [r["internal_id"] for r in normalized]
