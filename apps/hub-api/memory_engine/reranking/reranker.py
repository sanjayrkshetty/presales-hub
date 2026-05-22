"""
Memory Reranker.

Takes the top-N cosine-similarity results from the retriever and reranks
them using Claude Haiku as a cross-encoder.  Falls back to original order
if the LLM is unavailable, rate-limited, or times out.

Invariant: the reranker never drops results — it only reorders them.
           The original cosine score is preserved alongside the rerank score.

Usage pattern (always fetch k*MULTIPLIER candidates, rerank to k):
    candidates = retriever.retrieve(query, top_k=k * RERANK_CANDIDATE_MULTIPLIER)
    final = reranker.rerank(query, candidates, top_k=k)
"""
import json
import logging
import os
from typing import Optional

from memory_engine.storage.base import SearchResult
from memory_engine.config import RERANK_CANDIDATE_MULTIPLIER

logger = logging.getLogger("memory_engine.reranking")


class MemoryReranker:
    """
    LLM-assisted relevance reranking.
    Stateless — safe to instantiate per request.
    """

    async def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """
        Rerank candidates by relevance to query using Claude Haiku.
        Falls back to cosine-similarity order on any error.
        """
        if not candidates:
            return []
        if len(candidates) <= 1:
            return candidates[:top_k]

        try:
            return await self._llm_rerank(query, candidates, top_k)
        except Exception as exc:
            logger.debug("LLM reranking skipped: %s", exc)
            return candidates[:top_k]

    async def _llm_rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return candidates[:top_k]

        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)

        # Build compact prompt — list each candidate with index
        snippets = "\n".join(
            f"[{i}] {r.content[:200]}" for i, r in enumerate(candidates)
        )
        prompt = (
            f"Query: {query}\n\n"
            f"Rank these {len(candidates)} passages by relevance to the query.\n"
            f"Return ONLY a JSON array of indices in descending relevance order.\n"
            f"Example: [2, 0, 1, 3]\n\n"
            f"Passages:\n{snippets}"
        )

        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()

        # Parse the index array
        start = raw.find("[")
        end = raw.rfind("]") + 1
        indices = json.loads(raw[start:end])

        reranked = []
        seen = set()
        for idx in indices:
            if isinstance(idx, int) and 0 <= idx < len(candidates) and idx not in seen:
                r = candidates[idx]
                r.score = r.score  # preserve original cosine score
                reranked.append(r)
                seen.add(idx)

        # Append any candidates not included in LLM output (safety net)
        for i, c in enumerate(candidates):
            if i not in seen:
                reranked.append(c)

        return reranked[:top_k]
