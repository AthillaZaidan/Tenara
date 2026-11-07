"""custom orders: requests, validations, specs, quotes, inspections, amendments

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-08
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

REQUEST_STATUSES = ("draft", "submitted", "validating", "ready_for_quote", "awaiting_buyer",
                    "converted_to_order", "needs_revision", "rejected", "withdrawn")
REQ = ",".join(f"'{s}'" for s in REQUEST_STATUSES)
LINE_KINDS = ("fabric", "tailoring_base", "surcharge", "extra_material", "shipping_leg_1",
              "shipping_leg_2", "service_fee", "discount")
LINES = ",".join(f"'{s}'" for s in LINE_KINDS)


def _created_at():
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                     server_default=sa.func.now())


def _fk(name, target, ondelete=None, nullable=False):
    return sa.Column(name, sa.Uuid(), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "custom_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("buyer_id", "users.id", "CASCADE"),
        _fk("customization_id", "customizations.id"),
        _fk("listing_id", "fabric_listings.id"),
        _fk("merchant_id", "merchant_profiles.id"),
        _fk("tailor_id", "tailor_profiles.id"),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("address", postgresql.JSONB(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint(f"status in ({REQ})", name="ck_custom_requests_status_valid"),
    )
    op.create_table(
        "merchant_confirmations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("request_id", "custom_requests.id", "CASCADE"),
        sa.Column("request_revision", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(10), nullable=False),
        sa.Column("confirmed_price_idr", sa.BigInteger(), nullable=True),
        sa.Column("confirmed_quantity", sa.Numeric(10, 2), nullable=True),
        sa.Column("dispatch_days", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("valid", sa.Boolean(), nullable=False, server_default="true"),
        _fk("created_by", "users.id", "SET NULL", nullable=True),
        _created_at(),
        sa.CheckConstraint("decision in ('confirmed','rejected')",
                           name="ck_merchant_confirmations_decision_valid"),
    )
    op.create_table(
        "production_specs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("request_id", "custom_requests.id", "CASCADE"),
        sa.Column("request_revision", sa.Integer(), nullable=False),
        _fk("tailor_id", "tailor_profiles.id"),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("spec", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="issued"),
        _created_at(),
        sa.UniqueConstraint("request_id", "revision", name="uq_production_specs_request_rev"),
        sa.CheckConstraint("status in ('issued','superseded')", name="ck_production_specs_status_valid"),
    )
    op.create_table(
        "quotes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("request_id", "custom_requests.id", "CASCADE"),
        _fk("spec_id", "production_specs.id"),
        _fk("merchant_confirmation_id", "merchant_confirmations.id"),
        sa.Column("request_revision", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="issued"),
        sa.Column("total_idr", sa.BigInteger(), nullable=False),
        sa.Column("design_revision", sa.Integer(), nullable=False),
        sa.Column("measurement_set_id", sa.Uuid(), nullable=True),
        sa.Column("measurement_revision", sa.Integer(), nullable=True),
        sa.Column("commission", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.UniqueConstraint("request_id", "revision", name="uq_quotes_request_rev"),
        sa.CheckConstraint("status in ('issued','accepted','superseded','expired','declined')",
                           name="ck_quotes_status_valid"),
    )
    op.create_table(
        "quote_lines",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("quote_id", "quotes.id", "CASCADE"),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("amount_idr", sa.BigInteger(), nullable=False),
        sa.Column("owner", sa.String(10), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint(f"kind in ({LINES})", name="ck_quote_lines_kind_valid"),
        sa.CheckConstraint("owner in ('merchant','tailor','platform')", name="ck_quote_lines_owner_valid"),
    )
    op.create_table(
        "fabric_inspections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("order_id", "orders.id", "CASCADE"),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("measured_width_cm", sa.Numeric(6, 1), nullable=True),
        sa.Column("measured_length_m", sa.Numeric(8, 2), nullable=True),
        sa.Column("condition", sa.String(60), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        _fk("created_by", "users.id", "SET NULL", nullable=True),
        _created_at(),
    )
    op.create_table(
        "order_amendments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _fk("order_id", "orders.id", "CASCADE"),
        _fk("proposed_by", "users.id", "SET NULL", nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=False),
        sa.Column("price_delta_idr", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(10), nullable=False, server_default="proposed"),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.CheckConstraint("status in ('proposed','approved','rejected')",
                           name="ck_order_amendments_status_valid"),
    )
    # link columns on commerce tables
    op.add_column("orders", _fk("request_id", "custom_requests.id", nullable=True))
    op.create_unique_constraint("uq_orders_request", "orders", ["request_id"])
    op.add_column("demo_payments", _fk("quote_id", "quotes.id", "SET NULL", nullable=True))
    op.add_column("stock_reservations", _fk("quote_id", "quotes.id", "SET NULL", nullable=True))


def downgrade() -> None:
    op.drop_column("stock_reservations", "quote_id")
    op.drop_column("demo_payments", "quote_id")
    op.drop_constraint("uq_orders_request", "orders", type_="unique")
    op.drop_column("orders", "request_id")
    for table in ("order_amendments", "fabric_inspections", "quote_lines", "quotes",
                  "production_specs", "merchant_confirmations", "custom_requests"):
        op.drop_table(table)
