import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TEMPLATE_CODES = ("T01", "T02", "T03", "T04", "T05")


class PartnerApplication(Base):
    __tablename__ = "partner_applications"
    __table_args__ = (
        CheckConstraint("type in ('merchant','tailor')", name="ck_partner_applications_type_valid"),
        CheckConstraint(
            "status in ('draft','submitted','under_review','approved','needs_information',"
            "'rejected')",
            name="ck_partner_applications_status_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    applicant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="draft")
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PartnerReview(Base):
    __tablename__ = "partner_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("partner_applications.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MerchantProfile(Base):
    __tablename__ = "merchant_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_merchant_profiles_user"),
        CheckConstraint("status in ('active','suspended')", name="ck_merchant_profiles_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    shop_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    province: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TailorProfile(Base):
    __tablename__ = "tailor_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_tailor_profiles_user"),
        CheckConstraint("status in ('active','suspended')", name="ck_tailor_profiles_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    shop_name: Mapped[str] = mapped_column(String(200), nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    province: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    service_area: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default=text("'{}'::varchar[]")
    )
    experience_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TailorCapability(Base):
    __tablename__ = "tailor_capabilities"
    __table_args__ = (
        UniqueConstraint("tailor_id", "template_code", name="uq_tailor_capabilities_template"),
        CheckConstraint(
            "template_code in ('T01','T02','T03','T04','T05')",
            name="ck_tailor_capabilities_template_valid",
        ),
        CheckConstraint("base_rate_idr > 0", name="ck_tailor_capabilities_rate_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tailor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tailor_profiles.id", ondelete="CASCADE"), nullable=False
    )
    template_code: Mapped[str] = mapped_column(String(3), nullable=False)
    base_rate_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False)
    weekly_capacity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    materials: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default=text("'{}'::varchar[]")
    )
    supported_options: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    rate_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
