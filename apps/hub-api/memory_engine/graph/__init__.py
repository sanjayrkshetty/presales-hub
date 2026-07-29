"""
Knowledge Graph -- scrub-safe entity-relationship retrieval (thin B).

See knowledge.py for build/expand helpers used by the draft LangGraph.
"""
from memory_engine.graph.knowledge import (
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    build_from_chunks,
    expand_neighbourhood,
    expand_with_store_search,
)

__all__ = [
    "GraphEdge",
    "GraphNode",
    "KnowledgeGraph",
    "build_from_chunks",
    "expand_neighbourhood",
    "expand_with_store_search",
]