"""reference photos for checking a seller's tradition claim (SigLIP 2 image vectors)

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

DIM = 768


def upgrade() -> None:
    op.create_table(
        "reference_photos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entry_id", sa.Uuid(), sa.ForeignKey("gallery_entries.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("file_id", sa.Uuid(), sa.ForeignKey("files.id", ondelete="SET NULL"), nullable=True),
        sa.Column("listing_id", sa.Uuid(), sa.ForeignKey("fabric_listings.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("style", sa.String(10), nullable=False),
        sa.Column("source_label", sa.String(200), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("external_id", sa.String(300), nullable=True),
        sa.Column("credit", sa.String(300), nullable=True),
        sa.Column("license", sa.String(100), nullable=True),
        sa.Column("display_allowed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("embedding", Vector(DIM), nullable=False),
        sa.Column("embed_model", sa.String(100), nullable=False),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("decided_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("style in ('modern','archival')", name="ck_reference_photos_style_valid"),
        sa.CheckConstraint("approval_status in ('pending','approved','rejected')",
                           name="ck_reference_photos_status_valid"),
        sa.UniqueConstraint("external_id", name="uq_reference_photos_external_id"),
    )
    op.create_index("ix_reference_photos_embedding_hnsw", "reference_photos", ["embedding"],
                    postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64},
                    postgresql_ops={"embedding": "vector_cosine_ops"})
    op.create_index("ix_reference_photos_entry_status", "reference_photos", ["entry_id", "approval_status"])


def downgrade() -> None:
    op.drop_index("ix_reference_photos_entry_status", table_name="reference_photos")
    op.drop_index("ix_reference_photos_embedding_hnsw", table_name="reference_photos")
    op.drop_table("reference_photos")
