"""
Thin scrub-safe knowledge graph for hybrid retrieval (D-014 / Option B).

Nodes are metadata keys only — never real client names:
  bu, rfp_type, section, tech_tag

Edges: same_bu | same_rfp_type | same_section | shares_tech_tag
Expand vector hits by neighbourhood in the active chunk set.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

from memory_engine.storage.base import SearchResult


@dataclass
class GraphNode:
    node_id: str
    node_type: str  # bu | rfp_type | section | tech_tag
    label: str


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: str
    weight: float = 1.0


@dataclass
class KnowledgeGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    # chunk_id -> set of node_ids
    chunk_nodes: dict[str, set[str]] = field(default_factory=dict)


_TECH_HINTS = (
    "siem", "soar", "edr", "xdr", "dfir", "forensic", "incident", "retainer",
    "soc", "threat", "malware", "ir ", "containment", "triage",
)


def _tech_tags(text: str) -> set[str]:
    lower = (text or "").lower()
    return {t.strip() for t in _TECH_HINTS if t in lower}


def _meta(chunk: SearchResult) -> dict:
    meta = getattr(chunk, "metadata", None) or {}
    if isinstance(meta, str):
        try:
            import json
            meta = json.loads(meta)
        except Exception:
            meta = {}
    return meta if isinstance(meta, dict) else {}


def build_from_chunks(chunks: Iterable[SearchResult]) -> KnowledgeGraph:
    """Build an in-memory adjacency graph from retrieved/indexed chunks."""
    g = KnowledgeGraph()
    node_index: dict[str, GraphNode] = {}

    def add_node(node_type: str, label: str) -> str:
        nid = f"{node_type}:{label.lower().strip()}"
        if nid not in node_index:
            node_index[nid] = GraphNode(node_id=nid, node_type=node_type, label=label)
        return nid

    chunk_list = list(chunks)
    for c in chunk_list:
        meta = _meta(c)
        nids: set[str] = set()
        bu = meta.get("bu") or "shared"
        nids.add(add_node("bu", str(bu)))
        rfp = meta.get("rfp_type") or ""
        if rfp:
            nids.add(add_node("rfp_type", str(rfp)))
        section = c.section or meta.get("section") or ""
        if section:
            nids.add(add_node("section", str(section)))
        for tag in _tech_tags(c.content or ""):
            nids.add(add_node("tech_tag", tag))
        g.chunk_nodes[c.chunk_id] = nids

    # Edges between chunks that share a node
    by_node: dict[str, list[str]] = defaultdict(list)
    for cid, nids in g.chunk_nodes.items():
        for nid in nids:
            by_node[nid].append(cid)

    edge_set: set[tuple[str, str, str]] = set()
    for nid, cids in by_node.items():
        ntype = nid.split(":", 1)[0]
        edge_type = {
            "bu": "same_bu",
            "rfp_type": "same_rfp_type",
            "section": "same_section",
            "tech_tag": "shares_tech_tag",
        }.get(ntype, "related")
        for i, a in enumerate(cids):
            for b in cids[i + 1 :]:
                key = (min(a, b), max(a, b), edge_type)
                if key in edge_set:
                    continue
                edge_set.add(key)
                g.edges.append(GraphEdge(source_id=a, target_id=b, edge_type=edge_type))

    g.nodes = list(node_index.values())
    return g


def expand_neighbourhood(
    seed_chunks: list[SearchResult],
    pool: list[SearchResult],
    *,
    max_extra: int = 4,
) -> list[SearchResult]:
    """
    Given vector seed hits, add neighbour chunks from `pool` that share
    scrub-safe graph nodes. Dedupes by chunk_id; preserves seed order first.
    """
    if not seed_chunks:
        return []
    graph = build_from_chunks(list(seed_chunks) + list(pool))
    seed_ids = {c.chunk_id for c in seed_chunks}
    # adjacency
    adj: dict[str, set[str]] = defaultdict(set)
    for e in graph.edges:
        adj[e.source_id].add(e.target_id)
        adj[e.target_id].add(e.source_id)

    neighbour_ids: list[str] = []
    seen = set(seed_ids)
    for s in seed_chunks:
        for n in adj.get(s.chunk_id, ()):
            if n in seen:
                continue
            seen.add(n)
            neighbour_ids.append(n)
            if len(neighbour_ids) >= max_extra:
                break
        if len(neighbour_ids) >= max_extra:
            break

    pool_map = {c.chunk_id: c for c in pool}
    extras = [pool_map[i] for i in neighbour_ids if i in pool_map]
    # If pool didn't include neighbours, nothing to add
    return list(seed_chunks) + extras


def expand_with_store_search(
    seed_chunks: list[SearchResult],
    *,
    store_search_fn,
    query: str,
    bu: Optional[str] = None,
    top_k: int = 12,
    max_extra: int = 4,
) -> list[SearchResult]:
    """Widen retrieval: fetch a larger pool then expand graph neighbourhood."""
    metadata_filter = {"bu": bu} if bu else None
    pool = store_search_fn(
        query=query,
        top_k=top_k,
        memory_type="proposal",
        metadata_filter=metadata_filter,
    ) or []
    if not pool:
        pool = store_search_fn(query=query, top_k=top_k, memory_type="proposal") or []
    return expand_neighbourhood(seed_chunks, pool, max_extra=max_extra)
