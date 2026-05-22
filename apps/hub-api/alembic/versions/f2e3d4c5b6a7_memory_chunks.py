"""Add memory_chunks table for Enterprise Memory Engine.

Revision ID: f2e3d4c5b6a7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-23 00:00:00.000000

Notes on production upgrade path:
  - embedding_json stores a JSON array of floats in TEXT column.
  - When pgvector is available, run the following after this migration:
      ALTER TABLE memory_chunks
        ADD COLUMN embedding vector(1536)
        GENERATED ALWAYS AS (embedding_json::vector) STORED;
      CREATE INDEX ON memory_chunks USING hnsw (embedding vector_cosine_ops);
  - Until then, cosine similarity is computed application-side.
"""
from alembic import op
import sqlalchemy as sa

revision = "f2e3d4c5b6a7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("chunk_id", sa.String(48), nullable=False),
        sa.Column("memory_type", sa.Text, nullable=False),
        sa.Column("source_type", sa.Text, nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("source_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("section", sa.Text, nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding_json", sa.Text, nullable=True),
        sa.Column("embedding_model", sa.Text, nullable=False, server_default="local-hash-v1"),
        sa.Column("embedding_dims", sa.Integer, nullable=True),
        sa.Column("metadata_json", sa.Text, nullable=False, server_default="{}"),
        sa.Column("indexed_at", sa.DateTime, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
    )
    op.create_index("idx_memory_chunks_chunk_id", "memory_chunks", ["chunk_id"], unique=True)
    op.create_index("idx_memory_type_active", "memory_chunks", ["memory_type", "is_active"])
    op.create_index("idx_memory_source", "memory_chunks", ["source_type", "source_id"])


def downgrade() -> None:
    op.drop_table("memory_chunks")
