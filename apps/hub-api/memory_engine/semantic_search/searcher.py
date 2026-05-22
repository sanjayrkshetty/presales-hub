"""
SemanticSearcher — high-level search orchestration.

Wraps: MemoryRetriever → MemoryReranker → annotated SearchResponse.

Provides a single entry point for all retrieval operations with:
  - Configurable reranking (opt-in, async)
  - Relevance score normalization
  - Result deduplication by source_id (optionally)
  - Telemetry span per search call
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from memory_engine.retrieval.retriever import MemoryRetriever
from memory_engine.reranking.reranker import MemoryReranker
from memory_engine.storage.base import VectorStore, SearchResult
from memory_engine.config import DEFAULT_TOP_K, RERANK_CANDIDATE_MULTIPLIER
from telemetry.tracing import trace_span

logger = logging.getLogger("memory_engine.semantic_search")


@dataclass
class SearchResponse:
    query: str
    results: list[SearchResult]
    total_candidates: int
    reranked: bool
    memory_type: Optional[str]
    searched_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "results": [r.to_dict() for r in self.results],
            "total_candidates_before_rerank": self.total_candidates,
            "reranked": self.reranked,
            "memory_type": self.memory_type,
            "returned": len(self.results),
            "searched_at": self.searched_at,
        }


class SemanticSearcher:
    def __init__(self, store: VectorStore):
        self._retriever = MemoryRetriever(store)
        self._reranker = MemoryReranker()

    async def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        memory_type: Optional[str] = None,
        metadata_filter: Optional[dict] = None,
        rerank: bool = False,
        deduplicate_sources: bool = False,
    ) -> SearchResponse:
        """
        Full retrieval pipeline.

        rerank=True: fetch top_k * RERANK_CANDIDATE_MULTIPLIER candidates,
                     then rerank with LLM to final top_k.
        deduplicate_sources=True: return at most one chunk per source_id.
        """
        with trace_span("memory.semantic_search", metadata={
            "memory_type": memory_type, "top_k": top_k, "rerank": rerank,
        }):
            fetch_k = top_k * RERANK_CANDIDATE_MULTIPLIER if rerank else top_k
            candidates = self._retriever.retrieve(
                query=query,
                top_k=fetch_k,
                memory_type=memory_type,
                metadata_filter=metadata_filter,
            )
            total = len(candidates)

            if rerank and candidates:
                results = await self._reranker.rerank(query, candidates, top_k)
                reranked = True
            else:
                results = candidates[:top_k]
                reranked = False

            if deduplicate_sources:
                seen_sources = set()
                deduped = []
                for r in results:
                    if r.source_id not in seen_sources:
                        deduped.append(r)
                        seen_sources.add(r.source_id)
                results = deduped[:top_k]

            return SearchResponse(
                query=query,
                results=results,
                total_candidates=total,
                reranked=reranked,
                memory_type=memory_type,
            )
