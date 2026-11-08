"""product stories: a cultural story per listing, written from approved catalog chunks

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_stories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("listing_id", sa.Uuid(), sa.ForeignKey("fabric_listings.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("notes", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("seconds", sa.Numeric(6, 2), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('draft','published','superseded')",
                           name="ck_product_stories_status_valid"),
    )
    op.create_index("ix_product_stories_listing", "product_stories", ["listing_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_product_stories_listing", table_name="product_stories")
    op.drop_table("product_stories")
