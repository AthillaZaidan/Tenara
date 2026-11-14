import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FabricListing(Base):
    __tablename__ = "fabric_listings"
    __table_args__ = (
        CheckConstraint("selling_unit in ('meter','piece')", name="ck_fabric_listings_unit_valid"),
        CheckConstraint(
            "status in ('draft','published','archived')", name="ck_fabric_listings_status_valid"
        ),
        CheckConstraint("price_idr > 0", name="ck_fabric_listings_price_positive"),
        CheckConstraint("min_quantity > 0 and quantity_increment > 0",
                        name="ck_fabric_listings_quantity_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    merchant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("merchant_profiles.id", ondelete="CASCADE"), nullable=False
    )
    entry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("gallery_entries.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    material: Mapped[str | None] = mapped_column(String(100), nullable=True)
    weight_gsm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thickness_note: Mapped[str | None] = mapped_column(String(100), nullable=True)
    usable_width_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selling_unit: Mapped[str] = mapped_column(String(10), nullable=False)
    price_idr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    min_quantity: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default="1"
    )
    quantity_increment: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, server_default="1"
    )
    piece_length_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    piece_width_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    motif_orientation: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pattern_repeat_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    province: Mapped[str] = mapped_column(String(100), nullable=False)
    dispatch_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    merchant_claimed_origin: Mapped[str | None] = mapped_column(Text, nullable=True)
    curator_verified_origin: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_match: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ListingImage(Base):
    __tablename__ = "listing_images"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fabric_listings.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    caption: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class FabricStockUnit(Base):
    """Identical stock units. Meter listings: `quantity` continuous pieces of `length_m` each.
    Piece listings: `quantity` whole pieces (length_m unused)."""

    __tablename__ = "fabric_stock_units"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_fabric_stock_units_quantity_nonneg"),
        CheckConstraint("length_m is null or length_m > 0", name="ck_fabric_stock_units_length_pos"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fabric_listings.id", ondelete="CASCADE"), nullable=False
    )
    length_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProductStory(Base):
    """A cultural story for one listing, written from approved catalog chunks (writer + critic).

    The seller reviews a draft and publishes it; publishing supersedes the previous published story.
    citations hold the catalog chunks (and their source URLs) behind the culture sentences.
    """

    __tablename__ = "product_stories"
    __table_args__ = (
        CheckConstraint("status in ('draft','published','superseded')",
                        name="ck_product_stories_status_valid"),
        Index("ix_product_stories_listing", "listing_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fabric_listings.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    # [{"paragraph": 1, "text": "...", "sources": ["foto" | chunk id, ...]}] for per-sentence source chips
    sentences: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    notes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    seconds: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FabricMap(Base):
    """Where the zones and main motifs sit on a listing's fabric photo (see app/ml/vision/fabric_map).

    An AI estimate until the merchant confirms or corrects it. Buyers' motif layouts copy the regions
    they use into the design revision, so later edits here never change a submitted design.
    regions: [{"id": "z1" | "m1", "kind": "zone" | "motif", "label", "box": [x0, y0, x1, y1] (0..1),
               "repeats": int | null}]
    """
    __tablename__ = "fabric_maps"
    __table_args__ = (
        CheckConstraint("status in ('pending','estimated','confirmed','failed')",
                        name="ck_fabric_maps_status_valid"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("fabric_listings.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    regions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    status: Mapped[str] = mapped_column(String(12), nullable=False, server_default="pending")
    method: Mapped[str | None] = mapped_column(String(80), nullable=True)
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
