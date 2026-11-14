import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
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


def _ts():
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def _upd():
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(),
                         onupdate=func.now())


class GarmentTemplate(Base):
    __tablename__ = "garment_templates"
    __table_args__ = (
        CheckConstraint("code in ('T01','T02','T03','T04','T05')", name="ck_garment_templates_code"),
    )

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class TemplateVersion(Base):
    __tablename__ = "template_versions"
    __table_args__ = (UniqueConstraint("code", "version", name="uq_template_versions_code_version"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(3), ForeignKey("garment_templates.code"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    definition_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = _ts()


class MeasurementSet(Base):
    __tablename__ = "measurement_sets"
    __table_args__ = (
        CheckConstraint("status in ('draft','confirmed')", name="ck_measurement_sets_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="draft")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _upd()


class MeasurementValue(Base):
    __tablename__ = "measurement_values"
    __table_args__ = (
        UniqueConstraint("set_id", "key", name="uq_measurement_values_set_key"),
        CheckConstraint(
            "source in ('estimated','manual','corrected','manual_required','tailor')",
            name="ck_measurement_values_source_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("measurement_sets.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(40), nullable=False)
    value_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    original_value_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    quality_flag: Mapped[str | None] = mapped_column(String(30), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    updated_at: Mapped[datetime] = _upd()


class Customization(Base):
    __tablename__ = "customizations"
    __table_args__ = (
        CheckConstraint("template_code in ('T01','T02','T03','T04','T05')",
                        name="ck_customizations_template_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fabric_listings.id"), nullable=False
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("gallery_entries.id"), nullable=False
    )
    template_code: Mapped[str] = mapped_column(String(3), nullable=False)
    template_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("template_versions.id"), nullable=False
    )
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    measurement_set_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("measurement_sets.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _upd()


class DesignRevision(Base):
    __tablename__ = "design_revisions"
    __table_args__ = (
        UniqueConstraint("customization_id", "revision", name="uq_design_revisions_rev"),
        CheckConstraint("source in ('initial','prompt','manual','revert')",
                        name="ck_design_revisions_source_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customizations.id", ondelete="CASCADE"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[dict] = mapped_column(JSONB, nullable=False)
    changes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    interpretation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    open_clarifications: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    reverted_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = _ts()


class PromptRequest(Base):
    __tablename__ = "prompt_requests"
    __table_args__ = (
        CheckConstraint("status in ('proposed','applied','discarded','superseded')",
                        name="ck_prompt_requests_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customizations.id", ondelete="CASCADE"), nullable=False
    )
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    proposal: Mapped[dict] = mapped_column(JSONB, nullable=False)
    interpreter: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="proposed")
    resulting_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = _ts()


class MaterialEstimate(Base):
    __tablename__ = "material_estimates"
    __table_args__ = (
        CheckConstraint("status in ('current','superseded')",
                        name="ck_material_estimates_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customizations.id", ondelete="CASCADE"), nullable=False
    )
    design_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    measurement_set_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("measurement_sets.id", ondelete="SET NULL"), nullable=True
    )
    measurement_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    listing_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="current")
    created_at: Mapped[datetime] = _ts()


class Preview(Base):
    __tablename__ = "previews"
    __table_args__ = (
        CheckConstraint("kind in ('product','on_body','avatar_3d')", name="ck_previews_kind_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    customization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("customizations.id", ondelete="CASCADE"), nullable=False
    )
    design_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="queued")
    method: Mapped[str | None] = mapped_column(String(80), nullable=True)
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    body_photo_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("body_photos.id", ondelete="SET NULL"), nullable=True
    )
    # avatar_3d: the measurements the body was rebuilt from; the preview goes stale when they change
    measurement_set_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("measurement_sets.id", ondelete="SET NULL"), nullable=True
    )
    measurement_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = _ts()
    updated_at: Mapped[datetime] = _upd()
