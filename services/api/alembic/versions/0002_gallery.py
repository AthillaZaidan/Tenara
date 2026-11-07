"""gallery and culture tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

DIM = 384


def _created_at():
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def upgrade() -> None:
    op.create_table(
        "gallery_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, server_default="tradition"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("aliases", sa.ARRAY(sa.String()), nullable=False,
                  server_default=sa.text("'{}'::varchar[]")),
        sa.Column("textile_type", sa.String(100), nullable=True),
        sa.Column("technique", sa.String(100), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("community", sa.String(100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("embedding", Vector(DIM), nullable=True),
        sa.Column("is_demo_seed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        _created_at(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_gallery_entries_slug"),
        sa.CheckConstraint("kind in ('textile','motif','tradition')",
                           name="ck_gallery_entries_kind_valid"),
        sa.CheckConstraint("status in ('draft','in_review','published','archived')",
                           name="ck_gallery_entries_status_valid"),
    )

    op.create_table(
        "gallery_reference_images",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entry_id", sa.Uuid(),
                  sa.ForeignKey("gallery_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.Uuid(), sa.ForeignKey("files.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("caption", sa.String(300), nullable=True),
        sa.Column("credit", sa.String(200), nullable=True),
        sa.Column("license", sa.String(100), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "cultural_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("publisher", sa.String(200), nullable=True),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("license", sa.String(100), nullable=True),
        sa.Column("rights_notes", sa.Text(), nullable=True),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("decided_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        _created_at(),
        sa.CheckConstraint("approval_status in ('pending','approved','rejected')",
                           name="ck_cultural_sources_status_valid"),
    )

    op.create_table(
        "source_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_id", sa.Uuid(),
                  sa.ForeignKey("cultural_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_id", sa.Uuid(),
                  sa.ForeignKey("gallery_entries.id", ondelete="CASCADE"), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("locator", sa.String(200), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("embedding", Vector(DIM), nullable=True),
        _created_at(),
    )

    op.create_table(
        "stories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entry_id", sa.Uuid(),
                  sa.ForeignKey("gallery_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("unresolved", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        _created_at(),
        sa.UniqueConstraint("entry_id", "revision", name="uq_stories_entry_revision"),
        sa.CheckConstraint(
            "status in ('draft','in_review','approved','rejected','superseded')",
            name="ck_stories_status_valid",
        ),
    )

    op.create_table(
        "story_citations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("story_id", sa.Uuid(), sa.ForeignKey("stories.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("source_id", sa.Uuid(),
                  sa.ForeignKey("cultural_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), sa.ForeignKey("source_chunks.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("locator", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    for table in ("story_citations", "stories", "source_chunks", "cultural_sources",
                  "gallery_reference_images", "gallery_entries"):
        op.drop_table(table)
