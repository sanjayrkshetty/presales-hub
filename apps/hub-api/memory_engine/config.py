"""
Central configuration for the memory engine.
All tuneable constants live here so they propagate consistently.
"""
import os

# ── Embedding settings ─────────────────────────────────────────────────────

# Model used when OPENAI_API_KEY is set
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_EMBEDDING_DIMS = 1536

# Local hash provider (no API, deterministic, used in CI/test when MiniLM absent)
LOCAL_HASH_DIMS = 128
LOCAL_HASH_MODEL = "local-hash-v1"

# v1 semantic embeddings: sentence-transformers all-MiniLM-L6-v2 (CPU-friendly)
MINILM_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
MINILM_DIMS = 384
# Set EMBEDDING_PROVIDER=hash to force hash embeddings (CI / no torch)
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "auto")  # auto | minilm | hash | openai

# Active model version tag written to every chunk (bump when model changes
# to trigger re-indexing of stale embeddings)
EMBEDDING_MODEL_VERSION = os.getenv("EMBEDDING_MODEL_VERSION", MINILM_MODEL)

# ── Chunking settings ─────────────────────────────────────────────────────

CHUNK_MAX_CHARS = 800    # max characters per text chunk
CHUNK_OVERLAP_CHARS = 80  # overlap between consecutive chunks

# Minimum content length to index — very short strings carry no signal
MIN_CHUNK_CHARS = 20

# ── Retrieval settings ─────────────────────────────────────────────────────

DEFAULT_TOP_K = 5        # default number of results to return
MAX_TOP_K = 50           # hard ceiling (prevents full-table scan in cosine)
RERANK_CANDIDATE_MULTIPLIER = 3  # fetch k*3 candidates before reranking to k

# ── Storage settings ──────────────────────────────────────────────────────

# When DB_URL contains "postgresql", use PgVectorStore; else SqliteVectorStore
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./presales_hub.db")
USE_PGVECTOR = "postgresql" in DB_URL.lower()
