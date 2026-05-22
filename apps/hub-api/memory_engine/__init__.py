"""
Enterprise Memory Engine for Presales Hub.

Provides workflow-native institutional memory: proposal knowledge,
SME expertise, customer intelligence, approval rationale, solution patterns.

Architecture:
  embeddings/      — provider abstraction (local hash, OpenAI, extensible)
  storage/         — vector store abstraction (SQLite cosine sim, pgvector)
  chunking/        — deterministic content splitting
  indexing/        — orchestrates chunk → embed → deduplicate → store
  ingestion/       — domain-specific ingesters (proposal, approval, audit)
  retrieval/       — metadata pre-filtering + cosine similarity top-k
  reranking/       — LLM-assisted relevance reranking (optional)
  semantic_search/ — high-level search orchestration
  knowledge/       — domain memory modules (ProposalMemory, SMEMemory, …)
  graph/           — entity relationship graph (stub for future)
  evaluators/      — retrieval quality metrics (MRR, P@k, recall@k)

Invariants:
  - All numeric similarity scores are deterministic.
  - LLM reranking is optional enrichment, never the authoritative path.
  - Every chunk is traceable to its source (source_id, section, model).
  - Idempotent indexing via chunk_id (SHA-256 dedup).
"""
