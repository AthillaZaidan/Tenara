"""fabric maps: zones and main motifs on a listing's fabric photo (AI estimate, merchant-confirmed)

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-14
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fabric_maps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("listing_id", sa.Uuid(), sa.ForeignKey("fabric_listings.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("file_id", sa.Uuid(), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("regions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("method", sa.String(80), nullable=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("confirmed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status in ('pending','estimated','confirmed','failed')",
                           name="ck_fabric_maps_status_valid"),
    )


def downgrade() -> None:
    op.drop_table("fabric_maps")
