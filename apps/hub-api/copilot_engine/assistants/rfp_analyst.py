"""
RFP Analysis Copilot.

Capabilities:
  - Requirement extraction
  - Compliance mandate identification
  - Risk identification
  - Deliverable extraction
  - Stakeholder detection
  - Scope summary
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from copilot_engine.orchestration.copilot_runner import CopilotRunner, CopilotResponse
from copilot_engine.retrieval.context_retriever import ContextRetriever
from copilot_engine.providers.base import LLMProvider

# Register prompt at import time
import copilot_engine.prompts.rfp_analysis  # noqa: F401

logger = logging.getLogger("copilot_engine.assistants.rfp")

_EXPECTED_FIELDS = ["requirements", "compliance", "risks", "deliverables", "stakeholders", "scope_summary"]


class RfpAnalyst:
    def __init__(self, db: Session, provider: Optional[LLMProvider] = None):
        self._db = db
        self._runner = CopilotRunner(db, provider)
        self._retriever = ContextRetriever(db)

    async def analyze(
        self,
        rfp_text: str,
        session_id: Optional[str] = None,
    ) -> CopilotResponse:
        """Analyze an RFP document and extract structured intelligence."""
        # Retrieve similar historical RFPs from memory for grounding
        chunks = self._retriever.retrieve_for_rfp(rfp_text, top_k=6)
        memory_context = ContextRetriever.format_as_context(chunks)

        return await self._runner.run(
            prompt_name="rfp_analysis_v1",
            prompt_vars={
                "rfp_text": rfp_text[:3000],    # cap to avoid token overflow
                "memory_context": memory_context,
            },
            context_chunks=chunks,
            expected_json_fields=_EXPECTED_FIELDS,
        )
