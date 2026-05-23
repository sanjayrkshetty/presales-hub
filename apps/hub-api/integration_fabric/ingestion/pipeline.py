"""
Ingestion pipeline base.

Each pipeline: validate → extract → normalize → route → audit.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class IngestionResult:
    success: bool
    pipeline: str
    records_ingested: int = 0
    records_failed: int = 0
    artifact_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class IngestionPipeline(ABC):
    PIPELINE_NAME: str = ""
    SUPPORTED_SOURCES: list[str] = []

    @abstractmethod
    def validate(self, raw: Any) -> tuple[bool, list[str]]:
        """Validate raw input. Returns (valid, errors)."""

    @abstractmethod
    def extract(self, raw: Any) -> list[dict]:
        """Extract structured records from raw input."""

    @abstractmethod
    def normalize(self, records: list[dict]) -> list[dict]:
        """Normalize to platform-agnostic schema."""

    @abstractmethod
    def route(self, normalized: list[dict], db=None) -> list[str]:
        """Persist or route normalized records. Returns artifact IDs."""

    def run(self, raw: Any, db=None) -> IngestionResult:
        valid, errors = self.validate(raw)
        if not valid:
            return IngestionResult(success=False, pipeline=self.PIPELINE_NAME,
                                   error="; ".join(errors))
        try:
            records = self.extract(raw)
            normalized = self.normalize(records)
            artifact_ids = self.route(normalized, db)
            return IngestionResult(
                success=True,
                pipeline=self.PIPELINE_NAME,
                records_ingested=len(artifact_ids),
                artifact_ids=artifact_ids,
            )
        except Exception as exc:
            return IngestionResult(success=False, pipeline=self.PIPELINE_NAME, error=str(exc))
