"""
Decision Intelligence Layer for Presales Hub.

Provides deterministic, explainable, auditable intelligence assistance:
  scoring/         — proposal health + deal risk scoring
  predictors/      — SLA breach + workflow bottleneck prediction
  recommendations/ — SME ranking
  anomaly_detection/ — approval anomaly detection
  analytics/       — throughput + opportunity intelligence
  embeddings/      — future RAG infrastructure (stub)
  prompts/         — versioned LLM prompt templates + Langfuse tracing

All numeric outputs are deterministic (rules-based).
LLM calls are optional enrichment only — never the authoritative score.
"""
