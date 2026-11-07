import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _ts():
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PhotoConsent(Base):
    __tablename__ = "photo_consents"
    __table_args__ = (CheckConstraint("retention_minutes > 0", name="ck_photo_consents_retention"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(60), nullable=False)
    retention_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    share_original_with_tailor: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    allow_training_use: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    notice_version: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = _ts()
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BodyPhoto(Base):
    __tablename__ = "body_photos"
    __table_args__ = (
        CheckConstraint("status in ('stored','deleted')", name="ck_body_photos_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    consent_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("photo_consents.id"), nullable=False
    )
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="stored")
    delete_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _ts()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CvAnalysis(Base):
    __tablename__ = "cv_analyses"
    __table_args__ = (
        CheckConstraint("status in ('completed','failed')", name="ck_cv_analyses_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("fabric_listings.id", ondelete="SET NULL"), nullable=True
    )
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    method: Mapped[str] = mapped_column(String(120), nullable=False)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _ts()
