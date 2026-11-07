import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

ORDER_STATUSES = (
    "confirmed", "preparing", "shipped_to_buyer", "delivered", "completed", "issue_reported",
    "cancelled", "failed_fulfillment", "fabric_preparing", "shipped_to_tailor",
    "received_by_tailor", "inspection_passed", "in_production", "quality_check",
    "inspection_issue", "on_hold",
)
_STATUS_LIST = ",".join(f"'{s}'" for s in ORDER_STATUSES)


def _ts(**kw):
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), **kw)


class DeliveryAddress(Base):
    __tablename__ = "delivery_addresses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(60), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    line1: Mapped[str] = mapped_column(String(300), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    province: Mapped[str] = mapped_column(String(100), nullable=False)
    postal_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = _ts()


class CommissionRule(Base):
    __tablename__ = "commission_rules"
    __table_args__ = (
        CheckConstraint("applies_to in ('merchant_fabric','tailoring')",
                        name="ck_commission_rules_applies_valid"),
        CheckConstraint("rate_bps >= 0 and rate_bps <= 5000", name="ck_commission_rules_rate_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    applies_to: Mapped[str] = mapped_column(String(20), nullable=False)
    rate_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _ts()


class FabricCheckout(Base):
    __tablename__ = "fabric_checkouts"
    __table_args__ = (
        CheckConstraint(
            "status in ('review','payment_pending','paid','expired','cancelled','failed')",
            name="ck_fabric_checkouts_status_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fabric_listings.id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_price_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    subtotal_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shipping_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    service_fee_idr: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    total_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    address: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="review")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class StockReservation(Base):
    __tablename__ = "stock_reservations"
    __table_args__ = (
        CheckConstraint("status in ('held','committed','released','expired')",
                        name="ck_stock_reservations_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fabric_listings.id"), nullable=False
    )
    checkout_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fabric_checkouts.id", ondelete="SET NULL"), nullable=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quote_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("quotes.id", ondelete="SET NULL"), nullable=True
    )
    allocations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="held")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _ts()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fabric_listings.id", ondelete="CASCADE"), nullable=False
    )
    unit_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    length_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    reason: Mapped[str] = mapped_column(String(30), nullable=False)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    order_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = _ts()


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("checkout_id", name="uq_orders_checkout"),
        UniqueConstraint("request_id", name="uq_orders_request"),
        CheckConstraint("kind in ('fabric','custom')", name="ck_orders_kind_valid"),
        CheckConstraint(f"status in ({_STATUS_LIST})", name="ck_orders_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("merchant_profiles.id"), nullable=True
    )
    tailor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tailor_profiles.id"), nullable=True
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fabric_listings.id"), nullable=False
    )
    checkout_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fabric_checkouts.id"), nullable=True
    )
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("custom_requests.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="confirmed")
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    total_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DemoPayment(Base):
    __tablename__ = "demo_payments"
    __table_args__ = (
        UniqueConstraint("checkout_id", name="uq_demo_payments_checkout"),
        CheckConstraint(
            "status in ('not_started','pending','succeeded','failed','expired','refund_recorded')",
            name="ck_demo_payments_status_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    checkout_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fabric_checkouts.id", ondelete="SET NULL"), nullable=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    quote_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("quotes.id", ondelete="SET NULL"), nullable=True
    )
    amount_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    created_at: Mapped[datetime] = _ts()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OrderEvent(Base):
    __tablename__ = "order_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _ts()


class Shipment(Base):
    __tablename__ = "shipments"
    __table_args__ = (
        UniqueConstraint("order_id", "leg", name="uq_shipments_order_leg"),
        CheckConstraint("leg in ('merchant_to_buyer','merchant_to_tailor','tailor_to_buyer')",
                        name="ck_shipments_leg_valid"),
        CheckConstraint("status in ('pending','shipped','delivered')",
                        name="ck_shipments_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    leg: Mapped[str] = mapped_column(String(30), nullable=False)
    tracking_no: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    shipping_idr: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _ts()


class SettlementEntry(Base):
    __tablename__ = "settlement_entries"
    __table_args__ = (
        CheckConstraint("kind in ('sale','adjustment')", name="ck_settlement_entries_kind_valid"),
        CheckConstraint("party_role in ('merchant','tailor')",
                        name="ck_settlement_entries_role_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    party_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    party_role: Mapped[str] = mapped_column(String(10), nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    gross_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    commission_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    commission_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    net_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _ts()
