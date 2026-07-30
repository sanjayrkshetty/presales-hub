"""
G1 / Post-G1: thin knowledge-graph expand helpers.

Covers expand_neighbourhood and expand_with_store_search — scrub-safe
metadata nodes only (bu / rfp_type / section / tech_tag).
"""
from __future__ import annotations

from memory_engine.storage.base import SearchResult
from memory_engine.graph.knowledge import (
    expand_neighbourhood,
    expand_with_store_search,
)


def _chunk(
    chunk_id: str,
    content: str,
    *,
    section: str = "scope",
    score: float = 0.7,
    metadata: dict | None = None,
) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        memory_type="proposal",
        source_type="proposal",
        source_id=f"src-{chunk_id}",
        section=section,
        content=content,
        score=score,
        metadata=metadata or {},
    )


class TestExpandNeighbourhood:
    def test_adds_neighbours_sharing_bu_and_tech(self):
        seed = _chunk(
            "seed-1",
            "DFIR incident response with EDR containment",
            section="technical_approach",
            metadata={"bu": "dfir", "rfp_type": "DFIR"},
        )
        neighbour = _chunk(
            "nbr-1",
            "EDR triage playbook for DFIR retainer",
            section="methodology",
            metadata={"bu": "dfir", "rfp_type": "DFIR"},
        )
        unrelated = _chunk(
            "other-1",
            "generic cloud migration checklist",
            section="assumptions",
            metadata={"bu": "cloud", "rfp_type": "Cloud"},
        )

        out = expand_neighbourhood([seed], [seed, neighbour, unrelated], max_extra=4)

        ids = [c.chunk_id for c in out]
        assert ids[0] == "seed-1"
        assert "nbr-1" in ids
        assert "other-1" not in ids

    def test_empty_seeds_returns_empty(self):
        pool = [_chunk("p1", "siem soar content", metadata={"bu": "dfir"})]
        assert expand_neighbourhood([], pool) == []

    def test_respects_max_extra(self):
        seed = _chunk(
            "seed-1",
            "siem incident triage",
            section="scope",
            metadata={"bu": "dfir"},
        )
        pool = [seed] + [
            _chunk(
                f"nbr-{i}",
                "siem incident triage playbook",
                section="scope",
                metadata={"bu": "dfir"},
            )
            for i in range(6)
        ]
        out = expand_neighbourhood([seed], pool, max_extra=2)
        assert len(out) == 3  # seed + 2 extras
        assert out[0].chunk_id == "seed-1"

    def test_dedupes_seed_already_in_pool(self):
        seed = _chunk(
            "seed-1",
            "malware forensic analysis",
            metadata={"bu": "dfir"},
        )
        out = expand_neighbourhood([seed], [seed], max_extra=4)
        assert [c.chunk_id for c in out] == ["seed-1"]


class TestExpandWithStoreSearch:
    def test_widens_via_store_search_fn(self):
        seed = _chunk(
            "seed-1",
            "DFIR forensic collection with containment",
            section="technical_approach",
            metadata={"bu": "dfir", "rfp_type": "DFIR"},
        )
        pool_extra = _chunk(
            "pool-2",
            "forensic collection retainer for DFIR",
            section="methodology",
            metadata={"bu": "dfir", "rfp_type": "DFIR"},
        )

        calls: list[dict] = []

        def store_search_fn(**kwargs):
            calls.append(kwargs)
            return [seed, pool_extra]

        out = expand_with_store_search(
            [seed],
            store_search_fn=store_search_fn,
            query="DFIR forensic retainer",
            bu="dfir",
            top_k=12,
            max_extra=4,
        )

        assert calls
        assert calls[0]["metadata_filter"] == {"bu": "dfir"}
        assert calls[0]["memory_type"] == "proposal"
        ids = [c.chunk_id for c in out]
        assert ids[0] == "seed-1"
        assert "pool-2" in ids

    def test_retries_without_bu_filter_when_empty(self):
        seed = _chunk(
            "seed-1",
            "incident response EDR",
            metadata={"bu": "dfir"},
        )
        neighbour = _chunk(
            "nbr-1",
            "incident response EDR playbook",
            metadata={"bu": "dfir"},
        )
        calls: list[dict] = []

        def store_search_fn(**kwargs):
            calls.append(kwargs)
            if kwargs.get("metadata_filter"):
                return []
            return [seed, neighbour]

        out = expand_with_store_search(
            [seed],
            store_search_fn=store_search_fn,
            query="incident EDR",
            bu="dfir",
            max_extra=2,
        )

        assert len(calls) == 2
        assert calls[0]["metadata_filter"] == {"bu": "dfir"}
        assert calls[1].get("metadata_filter") is None
        assert "nbr-1" in [c.chunk_id for c in out]

    def test_empty_pool_returns_seeds_only(self):
        seed = _chunk("seed-1", "dfir content", metadata={"bu": "dfir"})

        def store_search_fn(**kwargs):
            return []

        out = expand_with_store_search(
            [seed],
            store_search_fn=store_search_fn,
            query="anything",
            bu="dfir",
        )
        assert [c.chunk_id for c in out] == ["seed-1"]
