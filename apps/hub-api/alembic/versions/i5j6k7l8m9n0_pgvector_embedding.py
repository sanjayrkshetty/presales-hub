"""Add pgvector embedding column to memory_chunks.

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-07-29 00:00:00.000000

Adds:
  - CREATE EXTENSION IF NOT EXISTS vector
  - memory_chunks.embedding vector(384)  (MiniLM dims; see memory_engine.config.MINILM_DIMS)
  - Backfill from embedding_json where parseable and dims match
  - Partial HNSW index on embedding (vector_cosine_ops) WHERE is_active
"""
from alembic import op

revision = "i5j6k7l8m9n0"
down_revision = "h4i5j6k7l8m9"
branch_labels = None
depends_on = None

# Locked: local all-MiniLM-L6-v2 → 384 dims
EMBEDDING_DIMS = 384


def upgrade() -> None:
    # Requires a pgvector-capable Postgres image (e.g. pgvector/pgvector:pg16)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        f"ALTER TABLE memory_chunks "
        f"ADD COLUMN IF NOT EXISTS embedding vector({EMBEDDING_DIMS})"
    )

    # Backfill from embedding_json when the JSON array length matches MiniLM dims.
    # CAST(embedding_json AS vector) works when the TEXT is a JSON array of floats.
    op.execute(
        f"""
        UPDATE memory_chunks
        SET embedding = embedding_json::vector
        WHERE embedding IS NULL
          AND embedding_json IS NOT NULL
          AND embedding_json <> ''
          AND (
            embedding_dims = {EMBEDDING_DIMS}
            OR (
              embedding_dims IS NULL
              AND jsonb_array_length(embedding_json::jsonb) = {EMBEDDING_DIMS}
            )
          )
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_memory_chunks_embedding_hnsw
        ON memory_chunks
        USING hnsw (embedding vector_cosine_ops)
        WHERE is_active
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_memory_chunks_embedding_hnsw")
    op.execute("ALTER TABLE memory_chunks DROP COLUMN IF EXISTS embedding")
    # Leave the vector extension installed (safe shared dependency).
