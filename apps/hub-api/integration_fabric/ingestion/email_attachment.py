"""Email attachment ingestion pipeline."""
from __future__ import annotations

import uuid
from integration_fabric.ingestion.pipeline import IngestionPipeline
from integration_fabric.config import INGESTION_SUPPORTED_MIME_TYPES


class EmailAttachmentPipeline(IngestionPipeline):
    PIPELINE_NAME = "email_attachment"
    SUPPORTED_SOURCES = ["gmail", "outlook"]

    def validate(self, raw: dict) -> tuple[bool, list[str]]:
        errors = []
        if not isinstance(raw, dict):
            return False, ["Input must be a dict"]
        if not raw.get("email_id"):
            errors.append("Missing 'email_id'")
        if not raw.get("attachments"):
            errors.append("No 'attachments' provided")
        return not errors, errors

    def extract(self, raw: dict) -> list[dict]:
        results = []
        for att in raw.get("attachments", []):
            results.append({
                "email_id": raw["email_id"],
                "subject": raw.get("subject", ""),
                "sender": raw.get("sender", ""),
                "filename": att.get("filename", ""),
                "mime_type": att.get("mime_type", ""),
                "content": att.get("content", ""),
                "size": att.get("size", 0),
            })
        return results

    def normalize(self, records: list[dict]) -> list[dict]:
        return [{
            "type": "email_attachment",
            "id": str(uuid.uuid4()),
            "email_id": r["email_id"],
            "subject": r["subject"],
            "sender": r["sender"],
            "filename": r["filename"],
            "mime_type": r["mime_type"],
            "content_preview": str(r["content"])[:200],
            "size_bytes": r["size"],
            "supported": r["mime_type"] in INGESTION_SUPPORTED_MIME_TYPES,
        } for r in records]

    def route(self, normalized: list[dict], db=None) -> list[str]:
        supported = [r for r in normalized if r["supported"]]
        return [r["id"] for r in supported]
