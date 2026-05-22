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

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Proposal, Opportunity
from copilot_engine.orchestration.copilot_runner import CopilotRunner, CopilotResponse
from copilot_engine.retrieval.context_retriever import ContextRetriever
from copilot_engine.context_builders.proposal_context import ProposalContextBuilder
from copilot_engine.providers.base import LLMProvider

import copilot_engine.prompts.proposal_drafting  # noqa: F401

logger = logging.getLogger("copilot_engine.assistants.proposal_drafter")


class ProposalDrafter:
    def __init__(self, db: Session, provider: Optional[LLMProvider] = None):
        self._db = db
        self._runner = CopilotRunner(db, provider)
        self._retriever = ContextRetriever(db)

    async def draft_section(
        self,
        proposal_id: str,
        section: str,
        user_query: str = "",
    ) -> CopilotResponse:
        """Draft a single proposal section grounded in similar historical proposals."""
        # Build proposal context
        ctx_builder = ProposalContextBuilder(self._db)
        ctx = ctx_builder.build(proposal_id)

        rfp_type = ctx.get("rfp_type") or ""
        stage = ctx.get("stage") or ""

        opp = ctx.get("opportunity") or {}
        opportunity_name = opp.get("title") or "Unknown opportunity"
        client_name = opp.get("client_id") or "Unknown client"

        # Retrieve similar proposals for grounding
        query = f"{section} {rfp_type} {user_query}".strip()
        chunks = self._retriever.retrieve_for_proposal(query, rfp_type=rfp_type, top_k=6)
        memory_context = ContextRetriever.format_as_context(chunks)

        return await self._runner.run(
            prompt_name="proposal_draft_section_v1",
            prompt_vars={
                "section": section,
                "memory_context": memory_context,
                "opportunity_name": opportunity_name,
                "client_name": client_name,
                "rfp_type": rfp_type,
                "stage": stage,
            },
            user_query=user_query or f"Draft the {section} section",
            context_chunks=chunks,
        )
