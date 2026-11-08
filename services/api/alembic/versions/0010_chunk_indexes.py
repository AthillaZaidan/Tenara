"""retrieval indexes on source chunks: HNSW (cosine) on embeddings, GIN on metadata

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-08
"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_source_chunks_embedding_hnsw", "source_chunks", ["embedding"],
                    postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64},
                    postgresql_ops={"embedding": "vector_cosine_ops"})
    op.create_index("ix_source_chunks_metadata_gin", "source_chunks", ["metadata"],
                    postgresql_using="gin", postgresql_ops={"metadata": "jsonb_path_ops"})


def downgrade() -> None:
    op.drop_index("ix_source_chunks_metadata_gin", table_name="source_chunks")
    op.drop_index("ix_source_chunks_embedding_hnsw", table_name="source_chunks")
