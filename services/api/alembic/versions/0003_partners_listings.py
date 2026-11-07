"""partners and listings

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _created_at():
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def _updated_at():
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def _uid(name, target, ondelete=None, nullable=False):
    return sa.Column(name, sa.Uuid(), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "partner_applications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _uid("applicant_id", "users.id", "CASCADE"),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint("type in ('merchant','tailor')", name="ck_partner_applications_type_valid"),
        sa.CheckConstraint(
            "status in ('draft','submitted','under_review','approved','needs_information',"
            "'rejected')",
            name="ck_partner_applications_status_valid",
        ),
    )

    op.create_table(
        "partner_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _uid("application_id", "partner_applications.id", "CASCADE"),
        _uid("reviewer_id", "users.id", "SET NULL", nullable=True),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        _created_at(),
    )

    op.create_table(
        "merchant_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _uid("user_id", "users.id", "CASCADE"),
        sa.Column("shop_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("province", sa.String(100), nullable=False),
        sa.Column("contact_phone", sa.String(40), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        _created_at(),
        sa.UniqueConstraint("user_id", name="uq_merchant_profiles_user"),
        sa.CheckConstraint("status in ('active','suspended')",
                           name="ck_merchant_profiles_status_valid"),
    )

    op.create_table(
        "tailor_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _uid("user_id", "users.id", "CASCADE"),
        sa.Column("shop_name", sa.String(200), nullable=False),
        sa.Column("bio", sa.Text(), nullable=False, server_default=""),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("province", sa.String(100), nullable=False),
        sa.Column("contact_phone", sa.String(40), nullable=True),
        sa.Column("service_area", sa.ARRAY(sa.String()), nullable=False,
                  server_default=sa.text("'{}'::varchar[]")),
        sa.Column("experience_years", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        _created_at(),
        sa.UniqueConstraint("user_id", name="uq_tailor_profiles_user"),
        sa.CheckConstraint("status in ('active','suspended')",
                           name="ck_tailor_profiles_status_valid"),
    )

    op.create_table(
        "tailor_capabilities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _uid("tailor_id", "tailor_profiles.id", "CASCADE"),
        sa.Column("template_code", sa.String(3), nullable=False),
        sa.Column("base_rate_idr", sa.BigInteger(), nullable=False),
        sa.Column("lead_time_days", sa.Integer(), nullable=False),
        sa.Column("weekly_capacity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("materials", sa.ARRAY(sa.String()), nullable=False,
                  server_default=sa.text("'{}'::varchar[]")),
        sa.Column("supported_options", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("rate_version", sa.Integer(), nullable=False, server_default="1"),
        _updated_at(),
        sa.UniqueConstraint("tailor_id", "template_code", name="uq_tailor_capabilities_template"),
        sa.CheckConstraint("template_code in ('T01','T02','T03','T04','T05')",
                           name="ck_tailor_capabilities_template_valid"),
        sa.CheckConstraint("base_rate_idr > 0", name="ck_tailor_capabilities_rate_positive"),
    )

    op.create_table(
        "fabric_listings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _uid("merchant_id", "merchant_profiles.id", "CASCADE"),
        _uid("entry_id", "gallery_entries.id"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("material", sa.String(100), nullable=True),
        sa.Column("weight_gsm", sa.Integer(), nullable=True),
        sa.Column("thickness_note", sa.String(100), nullable=True),
        sa.Column("usable_width_cm", sa.Integer(), nullable=True),
        sa.Column("selling_unit", sa.String(10), nullable=False),
        sa.Column("price_idr", sa.BigInteger(), nullable=False),
        sa.Column("min_quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("quantity_increment", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("piece_length_cm", sa.Integer(), nullable=True),
        sa.Column("piece_width_cm", sa.Integer(), nullable=True),
        sa.Column("motif_orientation", sa.String(50), nullable=True),
        sa.Column("pattern_repeat_cm", sa.Integer(), nullable=True),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("province", sa.String(100), nullable=False),
        sa.Column("dispatch_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("merchant_claimed_origin", sa.Text(), nullable=True),
        sa.Column("curator_verified_origin", sa.Text(), nullable=True),
        sa.Column("visual_match", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint("selling_unit in ('meter','piece')", name="ck_fabric_listings_unit_valid"),
        sa.CheckConstraint("status in ('draft','published','archived')",
                           name="ck_fabric_listings_status_valid"),
        sa.CheckConstraint("price_idr > 0", name="ck_fabric_listings_price_positive"),
        sa.CheckConstraint("min_quantity > 0 and quantity_increment > 0",
                           name="ck_fabric_listings_quantity_positive"),
    )

    op.create_table(
        "listing_images",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _uid("listing_id", "fabric_listings.id", "CASCADE"),
        _uid("file_id", "files.id", "CASCADE"),
        sa.Column("caption", sa.String(300), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "fabric_stock_units",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _uid("listing_id", "fabric_listings.id", "CASCADE"),
        sa.Column("length_m", sa.Numeric(8, 2), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        _created_at(),
        sa.CheckConstraint("quantity >= 0", name="ck_fabric_stock_units_quantity_nonneg"),
        sa.CheckConstraint("length_m is null or length_m > 0",
                           name="ck_fabric_stock_units_length_pos"),
    )


def downgrade() -> None:
    for table in ("fabric_stock_units", "listing_images", "fabric_listings", "tailor_capabilities",
                  "tailor_profiles", "merchant_profiles", "partner_reviews",
                  "partner_applications"):
        op.drop_table(table)
