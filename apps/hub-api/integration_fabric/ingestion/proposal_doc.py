"""Proposal document ingestion pipeline."""
from __future__ import annotations

import re
import uuid
from integration_fabric.ingestion.pipeline import IngestionPipeline


class ProposalDocPipeline(IngestionPipeline):
    PIPELINE_NAME = "proposal_doc"
    SUPPORTED_SOURCES = ["sharepoint", "gdrive", "manual", "email"]

    def validate(self, raw: dict) -> tuple[bool, list[str]]:
        errors = []
        if not isinstance(raw, dict):
            return False, ["Input must be a dict"]
        if not raw.get("content"):
            errors.append("Missing 'content'")
        return not errors, errors

    def extract(self, raw: dict) -> list[dict]:
        return [{
            "content": raw.get("content", ""),
            "filename": raw.get("filename", ""),
            "source": raw.get("source", "manual"),
            "opportunity_id": raw.get("opportunity_id"),
            "client_name": raw.get("client_name", ""),
            "metadata": raw.get("metadata", {}),
        }]

    def normalize(self, records: list[dict]) -> list[dict]:
        return [{
            "type": "proposal_doc",
            "internal_id": str(uuid.uuid4()),
            "filename": r["filename"],
            "source": r["source"],
            "opportunity_id": r.get("opportunity_id"),
            "client_name": r["client_name"],
            "content_preview": r["content"][:500],
            "word_count": len(r["content"].split()),
            "has_exec_summary": bool(re.search(r"executive summary", r["content"], re.IGNORECASE)),
            "has_pricing": bool(re.search(r"pricing|cost|fee|rate", r["content"], re.IGNORECASE)),
            "metadata": r["metadata"],
        } for r in records]

    def route(self, normalized: list[dict], db=None) -> list[str]:
        return [r["internal_id"] for r in normalized]
