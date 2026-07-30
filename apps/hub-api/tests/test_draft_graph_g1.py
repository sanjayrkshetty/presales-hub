"""
G1 / Post-G1: draft LangGraph routing + passes_hard_gate.

Uses MockLLMProvider only (no Groq). Patches MemoryRetriever.retrieve so
tests do not depend on vector store contents. In-memory SQLite via conftest.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

from models import Client, Opportunity, Proposal
from copilot_engine.providers.mock_provider import MockLLMProvider
from memory_engine.storage.base import SearchResult


# Shared DFIR vocabulary so keyword overlap can clear GROUNDING_HARD_MIN (0.35).
_CHUNK_TEXT = (
    "incident response retainer methodology includes forensic collection "
    "containment triage malware analysis and evidence preservation for DFIR engagements"
)

_PASSING_DRAFT = (
    "## exec_summary\n"
    "[Source: proposal-hist-001] Our incident response retainer methodology covers "
    "forensic collection and containment triage for DFIR engagements with evidence "
    "preservation.\n\n"
    "## scope\n"
    "[Context 1] Scope includes malware analysis and forensic collection under the "
    "retainer methodology."
)

# Fabrication patterns → hard-gate fail regardless of score.
_FAILING_DRAFT = (
    "## exec_summary\n"
    "We guarantee 100% secure delivery with ISO 27001 compliance and a $500,000 SLA.\n\n"
    "## scope\n"
    "Everything is covered with no vulnerabilities."
)


def _make_search_result(
    content: str,
    *,
    chunk_id: str = "cid-1",
    source_id: str = "src-1",
    score: float = 0.8,
    section: str = "exec_summary",
    metadata: dict | None = None,
) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        memory_type="proposal",
        source_type="proposal",
        source_id=source_id,
        section=section,
        content=content,
        score=score,
        metadata=metadata or {"bu": "dfir"},
    )


def _seed_proposal(db) -> str:
    client = Client(name="G1 Test Co")
    db.add(client)
    db.flush()
    opp = Opportunity(
        client_id=client.id,
        title="DFIR Retainer RFP",
        rfp_type="DFIR",
        stage="drafting",
    )
    db.add(opp)
    db.flush()
    proposal = Proposal(opportunity_id=opp.id, stage="drafting")
    db.add(proposal)
    db.commit()
    return proposal.id


class QueuedMockLLMProvider(MockLLMProvider):
    """MockLLMProvider that returns successive fixed texts (draft → repair)."""

    def __init__(self, texts: list[str]):
        super().__init__("")
        self._queue = list(texts)

    async def complete(self, system_prompt: str, user_prompt: str, max_tokens: int = 1024):
        if self._queue:
            self._fixed = self._queue.pop(0)
        return await super().complete(system_prompt, user_prompt, max_tokens)


# ══════════════════════════════════════════════════════════════════════════════
# TestPassesHardGate
# ══════════════════════════════════════════════════════════════════════════════

class TestPassesHardGate:
    def test_fabrication_fail(self):
        from copilot_engine.grounding.validator import (
            GroundingReport,
            passes_hard_gate,
        )

        report = GroundingReport(
            grounding_score=0.9,
            has_citations=True,
            keyword_overlap=0.8,
            fabrication_flags=["Specific dollar amount not sourced from context"],
            warnings=[],
        )
        assert passes_hard_gate(report) is False

    def test_empty_context_fail(self):
        from copilot_engine.grounding.validator import (
            GroundingReport,
            passes_hard_gate,
            validate_grounding,
        )

        report = validate_grounding("Some response text.", [], require_citations=False)
        assert any("No context chunks provided" in w for w in report.warnings)
        assert passes_hard_gate(report) is False

        # High score alone must not pass when context was empty (warning present).
        empty_warned = GroundingReport(
            grounding_score=0.5,
            has_citations=True,
            keyword_overlap=0.0,
            fabrication_flags=[],
            warnings=["No context chunks provided — response is ungrounded"],
        )
        assert passes_hard_gate(empty_warned, allow_empty_context=False) is False
        assert passes_hard_gate(empty_warned, allow_empty_context=True) is True

    def test_score_at_or_above_threshold_pass(self):
        from copilot_engine.grounding.validator import (
            GROUNDING_HARD_MIN,
            GroundingReport,
            passes_hard_gate,
            validate_grounding,
        )

        chunk = _make_search_result(_CHUNK_TEXT)
        report = validate_grounding(_PASSING_DRAFT, [chunk], require_citations=True)
        assert report.grounding_score >= GROUNDING_HARD_MIN
        assert not report.fabrication_flags
        assert passes_hard_gate(report) is True

        # Boundary: exactly min_score with no fabrication / empty-context warning.
        boundary = GroundingReport(
            grounding_score=GROUNDING_HARD_MIN,
            has_citations=True,
            keyword_overlap=0.1,
            fabrication_flags=[],
            warnings=[],
        )
        assert passes_hard_gate(boundary) is True


# ══════════════════════════════════════════════════════════════════════════════
# TestDraftGraphRouting (after_validate: emit / repair / fallback)
# ══════════════════════════════════════════════════════════════════════════════

class TestDraftGraphRouting:
    @pytest.mark.asyncio
    async def test_pass_emits_without_repair(self, db):
        from copilot_engine.graphs.draft_graph import run_draft_graph
        from memory_engine.retrieval.retriever import MemoryRetriever

        proposal_id = _seed_proposal(db)
        chunks = [_make_search_result(_CHUNK_TEXT)]
        provider = MockLLMProvider(_PASSING_DRAFT)

        with patch.object(MemoryRetriever, "retrieve", return_value=chunks):
            result = await run_draft_graph(
                db,
                proposal_id=proposal_id,
                brief="Need DFIR retainer proposal",
                bu="dfir",
                provider=provider,
            )

        assert result.meta["mode"] == "groq"
        assert result.meta["repair_count"] == 0
        assert result.section_map
        assert result.meta["grounding"].get("grounding_score", 0) >= 0.35

    @pytest.mark.asyncio
    async def test_repair_then_pass(self, db):
        from copilot_engine.graphs.draft_graph import run_draft_graph
        from memory_engine.retrieval.retriever import MemoryRetriever

        proposal_id = _seed_proposal(db)
        chunks = [_make_search_result(_CHUNK_TEXT)]
        provider = QueuedMockLLMProvider([_FAILING_DRAFT, _PASSING_DRAFT])

        with patch.object(MemoryRetriever, "retrieve", return_value=chunks):
            result = await run_draft_graph(
                db,
                proposal_id=proposal_id,
                brief="Need DFIR retainer proposal",
                bu="dfir",
                provider=provider,
            )

        assert result.meta["mode"] == "repaired"
        assert result.meta["repair_count"] == 1
        assert result.meta["grounding"].get("fabrication_flags") == []
        assert result.meta["grounding"].get("grounding_score", 0) >= 0.35

    @pytest.mark.asyncio
    async def test_fallback_after_failed_repair(self, db):
        from copilot_engine.graphs.draft_graph import run_draft_graph
        from memory_engine.retrieval.retriever import MemoryRetriever

        proposal_id = _seed_proposal(db)
        chunks = [_make_search_result(_CHUNK_TEXT)]
        # Both draft and repair fail the hard gate → after_validate → fallback.
        provider = QueuedMockLLMProvider([_FAILING_DRAFT, _FAILING_DRAFT])

        with patch.object(MemoryRetriever, "retrieve", return_value=chunks):
            result = await run_draft_graph(
                db,
                proposal_id=proposal_id,
                brief="Need DFIR retainer proposal",
                bu="dfir",
                provider=provider,
            )

        assert result.meta["mode"] == "template_fallback"
        assert result.meta["repair_count"] == 1
        assert "exec_summary" in result.section_map
        assert "fallback" in result.section_map["exec_summary"].lower() or (
            "scrubbed" in result.section_map["exec_summary"].lower()
        )
