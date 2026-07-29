"""
Proposal Drafting Copilot.

Capabilities:
  - Retrieve similar historical proposals
  - Draft individual sections grounded in memory
  - Suggest reusable content with source citations
  - Flag gaps requiring additional input
"""
import logging
from typing import Optional

from sqlalchemy.orm import Session

from copilot_engine.orchestration.copilot_runner import CopilotResponse
from copilot_engine.providers.base import LLMProvider
from copilot_engine.graphs.draft_graph import run_section_draft_graph

import copilot_engine.prompts.proposal_drafting  # noqa: F401

logger = logging.getLogger("copilot_engine.assistants.proposal_drafter")


class ProposalDrafter:
    def __init__(self, db: Session, provider: Optional[LLMProvider] = None):
        self._db = db
        self._provider = provider

    async def draft_section(
        self,
        proposal_id: str,
        section: str,
        user_query: str = "",
    ) -> CopilotResponse:
        """Draft a section using shared LangGraph (D-014)."""
        result = await run_section_draft_graph(
            self._db,
            proposal_id=proposal_id,
            section=section,
            user_query=user_query or f"Draft the {section} section",
            provider=self._provider,
        )
        meta = result.meta or {}
        grounding = (meta.get("grounding") or {})
        return CopilotResponse(
            content=result.content,
            provider=meta.get("provider", "none"),
            model=meta.get("model", "none"),
            prompt_name="proposal_draft_section_langgraph_v1",
            prompt_version="v1",
            input_tokens=int(meta.get("input_tokens", 0)),
            output_tokens=int(meta.get("output_tokens", 0)),
            latency_ms=float(meta.get("latency_ms", 0.0)),
            grounding={"score": grounding.get("grounding_score", 0.0), **grounding},
            evaluation={
                "quality_score": grounding.get("grounding_score", 0.0),
                "mode": meta.get("mode", ""),
                "repair_count": meta.get("repair_count", 0),
            },
            safety_warnings=list(grounding.get("warnings", [])),
            retrieved_chunks=int(meta.get("retrieved_chunks", len(result.chunks or []))),
        )
