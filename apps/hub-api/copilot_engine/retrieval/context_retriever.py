"""
RAG context retriever for copilot grounding.

Wraps memory_engine retrieval with copilot-specific query strategies per memory type.
Returns formatted context blocks ready to inject into LLM prompts.
"""
from sqlalchemy.orm import Session

from memory_engine.retrieval.retriever import MemoryRetriever
from memory_engine.storage.factory import get_vector_store
from memory_engine.storage.base import SearchResult
from copilot_engine.config import MAX_CONTEXT_CHUNKS


class ContextRetriever:
    def __init__(self, db: Session):
        store = get_vector_store(db)
        self._retriever = MemoryRetriever(store)

    def retrieve_for_rfp(self, rfp_text: str, top_k: int = MAX_CONTEXT_CHUNKS) -> list[SearchResult]:
        """Retrieve similar historical proposals and solutions for RFP context."""
        return self._retriever.retrieve(
            query=rfp_text[:500],
            top_k=top_k,
        )

    def retrieve_for_proposal(
        self,
        query: str,
        rfp_type: str = None,
        top_k: int = MAX_CONTEXT_CHUNKS,
    ) -> list[SearchResult]:
        """Retrieve similar proposals for drafting assistance."""
        metadata_filter = {"rfp_type": rfp_type} if rfp_type else None
        return self._retriever.retrieve(
            query=query,
            top_k=top_k,
            memory_type="proposal",
            metadata_filter=metadata_filter,
        )

    def retrieve_for_approval(
        self,
        query: str,
        stage: str = None,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Retrieve historical approval rationale for comparison."""
        metadata_filter = {"stage": stage} if stage else None
        return self._retriever.retrieve(
            query=query,
            top_k=top_k,
            memory_type="approval",
            metadata_filter=metadata_filter,
        )

    def retrieve_for_solution(
        self,
        query: str,
        rfp_type: str = None,
        top_k: int = MAX_CONTEXT_CHUNKS,
    ) -> list[SearchResult]:
        """Retrieve solution patterns for architecture suggestions."""
        metadata_filter = {"rfp_type": rfp_type} if rfp_type else None
        return self._retriever.retrieve(
            query=query,
            top_k=top_k,
            memory_type="solution",
            metadata_filter=metadata_filter,
        )

    def retrieve_for_workflow(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Retrieve delivery and audit patterns for workflow guidance."""
        return self._retriever.retrieve(
            query=query,
            top_k=top_k,
            memory_type="delivery",
        )

    @staticmethod
    def format_as_context(chunks: list[SearchResult]) -> str:
        """Format SearchResult list into LLM-readable numbered context block."""
        if not chunks:
            return "No relevant historical context found."
        lines: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            src = chunk.source_id
            section = chunk.section or "unknown"
            score = round(chunk.score, 3)
            lines.append(
                f"[Context {i} | Source: {src} | Section: {section} | Score: {score}]"
            )
            lines.append(chunk.content[:600])
            lines.append("")
        return "\n".join(lines)
