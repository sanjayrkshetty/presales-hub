"""
Retrieval Quality Evaluators.

Computes standard IR metrics for validating retrieval systems:
  MRR@k    (Mean Reciprocal Rank)
  P@k      (Precision at k)
  Recall@k

All functions are pure Python — no external dependencies.

Usage in tests:
    from memory_engine.evaluators.retrieval_eval import mrr_at_k, precision_at_k

Usage in CI/evaluation pipelines:
    dataset = [
        {"query": "...", "relevant_ids": ["chunk-a", "chunk-b"]},
        ...
    ]
    avg_mrr = avg_mrr_at_k(dataset, retrieved_fn, k=5)
"""
from typing import Callable, Optional


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    """Reciprocal rank of the first relevant result in retrieved list."""
    for i, cid in enumerate(retrieved, start=1):
        if cid in relevant:
            return 1.0 / i
    return 0.0


def mrr_at_k(
    queries: list[dict],   # [{query, relevant_ids: list[str]}]
    retrieved: list[list[str]],  # parallel list of retrieved chunk_ids
    k: int = 5,
) -> float:
    """Mean Reciprocal Rank @ k across all queries."""
    if not queries:
        return 0.0
    scores = []
    for q, ret in zip(queries, retrieved):
        relevant = set(q.get("relevant_ids", []))
        rr = reciprocal_rank(ret[:k], relevant)
        scores.append(rr)
    return sum(scores) / len(scores)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of top-k retrieved that are relevant."""
    if k == 0:
        return 0.0
    hits = sum(1 for cid in retrieved[:k] if cid in relevant)
    return hits / k


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of all relevant items found in top-k."""
    if not relevant:
        return 0.0
    hits = sum(1 for cid in retrieved[:k] if cid in relevant)
    return hits / len(relevant)


def avg_precision_at_k(
    queries: list[dict],
    retrieved: list[list[str]],
    k: int = 5,
) -> float:
    """Mean Precision @ k across all queries."""
    if not queries:
        return 0.0
    scores = [
        precision_at_k(ret, set(q.get("relevant_ids", [])), k)
        for q, ret in zip(queries, retrieved)
    ]
    return sum(scores) / len(scores)


def avg_recall_at_k(
    queries: list[dict],
    retrieved: list[list[str]],
    k: int = 5,
) -> float:
    """Mean Recall @ k across all queries."""
    if not queries:
        return 0.0
    scores = [
        recall_at_k(ret, set(q.get("relevant_ids", [])), k)
        for q, ret in zip(queries, retrieved)
    ]
    return sum(scores) / len(scores)


def evaluate_retrieval(
    queries: list[dict],
    retrieved: list[list[str]],
    k: int = 5,
) -> dict:
    """Full evaluation report for a retrieval system."""
    return {
        "k": k,
        "num_queries": len(queries),
        "mrr_at_k": round(mrr_at_k(queries, retrieved, k), 4),
        "precision_at_k": round(avg_precision_at_k(queries, retrieved, k), 4),
        "recall_at_k": round(avg_recall_at_k(queries, retrieved, k), 4),
    }
