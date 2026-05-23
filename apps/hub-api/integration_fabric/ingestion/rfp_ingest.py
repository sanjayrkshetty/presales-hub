"""Inbound RFP document ingestion pipeline."""
from __future__ import annotations

import re
import uuid
from integration_fabric.ingestion.pipeline import IngestionPipeline, IngestionResult
from integration_fabric.config import INGESTION_MAX_FILE_SIZE_BYTES, INGESTION_SUPPORTED_MIME_TYPES


class RFPIngestionPipeline(IngestionPipeline):
    PIPELINE_NAME = "rfp_ingest"
    SUPPORTED_SOURCES = ["email", "sharepoint", "gdrive", "manual"]

    def validate(self, raw: dict) -> tuple[bool, list[str]]:
        errors = []
        if not isinstance(raw, dict):
            return False, ["Input must be a dict with 'content', 'filename', 'mime_type'"]
        if not raw.get("content"):
            errors.append("Missing 'content'")
        if not raw.get("filename"):
            errors.append("Missing 'filename'")
        mime = raw.get("mime_type", "")
        if mime and mime not in INGESTION_SUPPORTED_MIME_TYPES:
            errors.append(f"Unsupported mime_type '{mime}'")
        size = raw.get("size_bytes", 0)
        if size > INGESTION_MAX_FILE_SIZE_BYTES:
            errors.append(f"File size {size} exceeds limit {INGESTION_MAX_FILE_SIZE_BYTES}")
        return not errors, errors

    def extract(self, raw: dict) -> list[dict]:
        content = raw.get("content", "")
        return [{
            "filename": raw.get("filename", ""),
            "source": raw.get("source", "manual"),
            "content": content,
            "mime_type": raw.get("mime_type", ""),
            "metadata": raw.get("metadata", {}),
            "sections": self._extract_sections(content),
            "requirements": self._extract_requirements(content),
        }]

    def _extract_sections(self, content: str) -> list[str]:
        patterns = [r"(?:^|\n)(#{1,3}\s+.+)", r"(?:^|\n)(\d+\.\s+.+)", r"(?:^|\n)([A-Z][A-Z\s]+:)"]
        found = []
        for p in patterns:
            found.extend(re.findall(p, content))
        return [s.strip() for s in found[:20]]

    def _extract_requirements(self, content: str) -> list[str]:
        patterns = [
            r"(?:must|shall|required|mandatory)[^\.\n]{10,80}",
            r"requirement[s]?[:\s]+[^\.\n]{10,80}",
        ]
        reqs = []
        for p in patterns:
            reqs.extend(re.findall(p, content, re.IGNORECASE))
        return reqs[:30]

    def normalize(self, records: list[dict]) -> list[dict]:
        normalized = []
        for r in records:
            normalized.append({
                "type": "rfp",
                "id": str(uuid.uuid4()),
                "filename": r["filename"],
                "source": r["source"],
                "content_preview": r["content"][:500],
                "section_count": len(r["sections"]),
                "requirement_count": len(r["requirements"]),
                "requirements": r["requirements"],
                "metadata": r["metadata"],
            })
        return normalized

    def route(self, normalized: list[dict], db=None) -> list[str]:
        return [r["id"] for r in normalized]
