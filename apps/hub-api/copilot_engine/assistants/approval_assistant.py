"""
Approval Reasoning Assistant.

Capabilities:
  - Explain approval rationale from decision notes
  - Highlight risk areas flagged in decisions
  - Surface anomalies (timing, actor patterns)
  - Compare against historical approvals from memory
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from copilot_engine.orchestration.copilot_runner import CopilotRunner, CopilotResponse
from copilot_engine.retrieval.context_retriever import ContextRetriever
from copilot_engine.context_builders.approval_context import ApprovalContextBuilder
from copilot_engine.providers.base import LLMProvider

import copilot_engine.prompts.approval_assist  # noqa: F401

logger = logging.getLogger("copilot_engine.assistants.approval")

_EXPECTED_FIELDS = [
    "rationale_summary", "risk_areas", "anomaly_flags",
    "historical_comparison", "recommended_follow_up",
]


class ApprovalAssistant:
    def __init__(self, db: Session, provider: Optional[LLMProvider] = None):
        self._db = db
        self._runner = CopilotRunner(db, provider)
        self._retriever = ContextRetriever(db)

    async def explain(self, approval_id: str) -> CopilotResponse:
        """Explain an approval decision with historical comparison."""
        ctx_builder = ApprovalContextBuilder(self._db)
        ctx = ctx_builder.build(approval_id)
        approval_text = ApprovalContextBuilder.to_text(ctx)

        # Build search query from the approval's stage and status
        stage = ctx.get("stage") or ""
        status = ctx.get("status") or ""
        query = f"{stage} {status} approval decision rationale"

        chunks = self._retriever.retrieve_for_approval(query, stage=stage, top_k=5)
        memory_context = ContextRetriever.format_as_context(chunks)

        return await self._runner.run(
            prompt_name="approval_assist_v1",
            prompt_vars={
                "approval_id": approval_id,
                "approval_context": approval_text,
                "memory_context": memory_context,
            },
            context_chunks=chunks,
            expected_json_fields=_EXPECTED_FIELDS,
        )
