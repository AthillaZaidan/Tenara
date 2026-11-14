"""Add curated motif variants and optional merchant listing association."""
import sqlalchemy as sa

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gallery_variants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entry_id", sa.Uuid(), sa.ForeignKey("gallery_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("entry_id", "name", name="uq_gallery_variant_name"),
    )
    op.create_index("ix_gallery_variants_entry_id", "gallery_variants", ["entry_id"])
    op.create_table(
        "gallery_variant_images",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("variant_id", sa.Uuid(), sa.ForeignKey("gallery_variants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.Uuid(), sa.ForeignKey("files.id"), nullable=False),
        sa.Column("caption", sa.String(300)), sa.Column("credit", sa.String(200)),
        sa.Column("license", sa.String(100)), sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_gallery_variant_images_variant_id", "gallery_variant_images", ["variant_id"])
    op.add_column("fabric_listings", sa.Column("variant_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_listing_variant", "fabric_listings", "gallery_variants", ["variant_id"], ["id"])
    op.create_index("ix_fabric_listings_variant_id", "fabric_listings", ["variant_id"])


def downgrade() -> None:
    op.drop_index("ix_fabric_listings_variant_id", table_name="fabric_listings")
    op.drop_constraint("fk_listing_variant", "fabric_listings", type_="foreignkey")
    op.drop_column("fabric_listings", "variant_id")
    op.drop_table("gallery_variant_images")
    op.drop_table("gallery_variants")
