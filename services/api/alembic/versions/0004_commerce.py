"""commerce: addresses, checkouts, reservations, orders, payments, shipments, settlement

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

ORDER_STATUSES = (
    "confirmed", "preparing", "shipped_to_buyer", "delivered", "completed", "issue_reported",
    "cancelled", "failed_fulfillment", "fabric_preparing", "shipped_to_tailor",
    "received_by_tailor", "inspection_passed", "in_production", "quality_check",
    "inspection_issue", "on_hold",
)
STATUS_LIST = ",".join(f"'{s}'" for s in ORDER_STATUSES)


def _created_at():
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def _updated_at():
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def _fk(name, target, ondelete=None, nullable=False):
    return sa.Column(name, sa.Uuid(), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "delivery_addresses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("user_id", "users.id", "CASCADE"),
        sa.Column("label", sa.String(60), nullable=False),
        sa.Column("recipient_name", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("line1", sa.String(300), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("province", sa.String(100), nullable=False),
        sa.Column("postal_code", sa.String(10), nullable=True),
        _created_at(),
    )

    op.create_table(
        "commission_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("applies_to", sa.String(20), nullable=False),
        sa.Column("rate_bps", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        _fk("created_by", "users.id", "SET NULL", nullable=True),
        _created_at(),
        sa.CheckConstraint("applies_to in ('merchant_fabric','tailoring')",
                           name="ck_commission_rules_applies_valid"),
        sa.CheckConstraint("rate_bps >= 0 and rate_bps <= 5000",
                           name="ck_commission_rules_rate_range"),
    )

    op.create_table(
        "fabric_checkouts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("buyer_id", "users.id", "CASCADE"),
        _fk("listing_id", "fabric_listings.id"),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit_price_idr", sa.BigInteger(), nullable=False),
        sa.Column("subtotal_idr", sa.BigInteger(), nullable=False),
        sa.Column("shipping_idr", sa.BigInteger(), nullable=False),
        sa.Column("service_fee_idr", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_idr", sa.BigInteger(), nullable=False),
        sa.Column("address", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="review"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "status in ('review','payment_pending','paid','expired','cancelled','failed')",
            name="ck_fabric_checkouts_status_valid",
        ),
    )

    op.create_table(
        "stock_reservations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("listing_id", "fabric_listings.id"),
        _fk("checkout_id", "fabric_checkouts.id", "SET NULL", nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("allocations", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="held"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        _created_at(),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status in ('held','committed','released','expired')",
                           name="ck_stock_reservations_status_valid"),
    )

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("listing_id", "fabric_listings.id", "CASCADE"),
        sa.Column("unit_id", sa.Uuid(), nullable=True),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("length_m", sa.Numeric(8, 2), nullable=True),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=True),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        _created_at(),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False),
        _fk("buyer_id", "users.id", "CASCADE"),
        _fk("merchant_id", "merchant_profiles.id", nullable=True),
        _fk("tailor_id", "tailor_profiles.id", nullable=True),
        _fk("listing_id", "fabric_listings.id"),
        _fk("checkout_id", "fabric_checkouts.id", nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="confirmed"),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("total_idr", sa.BigInteger(), nullable=False),
        _created_at(),
        _updated_at(),
        sa.UniqueConstraint("checkout_id", name="uq_orders_checkout"),
        sa.CheckConstraint("kind in ('fabric','custom')", name="ck_orders_kind_valid"),
        sa.CheckConstraint(f"status in ({STATUS_LIST})", name="ck_orders_status_valid"),
    )

    op.create_table(
        "demo_payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("checkout_id", "fabric_checkouts.id", "SET NULL", nullable=True),
        _fk("order_id", "orders.id", "SET NULL", nullable=True),
        sa.Column("amount_idr", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        _created_at(),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("checkout_id", name="uq_demo_payments_checkout"),
        sa.CheckConstraint(
            "status in ('not_started','pending','succeeded','failed','expired','refund_recorded')",
            name="ck_demo_payments_status_valid",
        ),
    )

    op.create_table(
        "order_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("order_id", "orders.id", "CASCADE"),
        _fk("actor_id", "users.id", "SET NULL", nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("from_status", sa.String(40), nullable=True),
        sa.Column("to_status", sa.String(40), nullable=True),
        sa.Column("simulated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("note", sa.Text(), nullable=True),
        _created_at(),
    )

    op.create_table(
        "shipments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("order_id", "orders.id", "CASCADE"),
        sa.Column("leg", sa.String(30), nullable=False),
        sa.Column("tracking_no", sa.String(60), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("shipping_idr", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.UniqueConstraint("order_id", "leg", name="uq_shipments_order_leg"),
        sa.CheckConstraint(
            "leg in ('merchant_to_buyer','merchant_to_tailor','tailor_to_buyer')",
            name="ck_shipments_leg_valid",
        ),
        sa.CheckConstraint("status in ('pending','shipped','delivered')",
                           name="ck_shipments_status_valid"),
    )

    op.create_table(
        "settlement_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("order_id", "orders.id", "CASCADE"),
        _fk("party_user_id", "users.id", "CASCADE"),
        sa.Column("party_role", sa.String(10), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("gross_idr", sa.BigInteger(), nullable=False),
        sa.Column("commission_bps", sa.Integer(), nullable=False),
        sa.Column("commission_idr", sa.BigInteger(), nullable=False),
        sa.Column("net_idr", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        _created_at(),
        sa.CheckConstraint("kind in ('sale','adjustment')", name="ck_settlement_entries_kind_valid"),
        sa.CheckConstraint("party_role in ('merchant','tailor')",
                           name="ck_settlement_entries_role_valid"),
    )


def downgrade() -> None:
    for table in ("settlement_entries", "shipments", "order_events", "demo_payments", "orders",
                  "stock_movements", "stock_reservations", "fabric_checkouts", "commission_rules",
                  "delivery_addresses"):
        op.drop_table(table)
