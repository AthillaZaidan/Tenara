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

REQUEST_STATUSES = ("draft", "submitted", "validating", "ready_for_quote", "awaiting_buyer",
                    "converted_to_order", "needs_revision", "rejected", "withdrawn")
_REQ = ",".join(f"'{s}'" for s in REQUEST_STATUSES)
LINE_KINDS = ("fabric", "tailoring_base", "surcharge", "extra_material", "shipping_leg_1",
              "shipping_leg_2", "service_fee", "discount")
_LINES = ",".join(f"'{s}'" for s in LINE_KINDS)


def _ts():
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CustomRequest(Base):
    __tablename__ = "custom_requests"
    __table_args__ = (CheckConstraint(f"status in ({_REQ})", name="ck_custom_requests_status_valid"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    customization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customizations.id"), nullable=False
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fabric_listings.id"), nullable=False
    )
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("merchant_profiles.id"), nullable=False
    )
    tailor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tailor_profiles.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="draft")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    address: Mapped[dict] = mapped_column(JSONB, nullable=False)
    snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class MerchantConfirmation(Base):
    __tablename__ = "merchant_confirmations"
    __table_args__ = (
        CheckConstraint("decision in ('confirmed','rejected')",
                        name="ck_merchant_confirmations_decision_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("custom_requests.id", ondelete="CASCADE"), nullable=False
    )
    request_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    confirmed_price_idr: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    confirmed_quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    dispatch_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _ts()


class ProductionSpec(Base):
    __tablename__ = "production_specs"
    __table_args__ = (
        UniqueConstraint("request_id", "revision", name="uq_production_specs_request_rev"),
        CheckConstraint("status in ('issued','superseded')", name="ck_production_specs_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("custom_requests.id", ondelete="CASCADE"), nullable=False
    )
    request_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    tailor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tailor_profiles.id"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    spec: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="issued")
    created_at: Mapped[datetime] = _ts()


class Quote(Base):
    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint("request_id", "revision", name="uq_quotes_request_rev"),
        CheckConstraint("status in ('issued','accepted','superseded','expired','declined')",
                        name="ck_quotes_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("custom_requests.id", ondelete="CASCADE"), nullable=False
    )
    spec_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("production_specs.id"), nullable=False)
    merchant_confirmation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("merchant_confirmations.id"), nullable=False
    )
    request_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="issued")
    total_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    design_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    measurement_set_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    measurement_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commission: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _ts()


class QuoteLine(Base):
    __tablename__ = "quote_lines"
    __table_args__ = (
        CheckConstraint(f"kind in ({_LINES})", name="ck_quote_lines_kind_valid"),
        CheckConstraint("owner in ('merchant','tailor','platform')", name="ck_quote_lines_owner_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    quote_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    amount_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    owner: Mapped[str] = mapped_column(String(10), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class FabricInspection(Base):
    __tablename__ = "fabric_inspections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    measured_width_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), nullable=True)
    measured_length_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    condition: Mapped[str] = mapped_column(String(60), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _ts()


class OrderAmendment(Base):
    __tablename__ = "order_amendments"
    __table_args__ = (
        CheckConstraint("status in ('proposed','approved','rejected')",
                        name="ck_order_amendments_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    proposed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    changes: Mapped[dict] = mapped_column(JSONB, nullable=False)
    price_delta_idr: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="proposed")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _ts()
