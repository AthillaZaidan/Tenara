import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppValidationError, Forbidden, NotFound
from app.core.revision import check_revision
from app.models import (
    FabricListing,
    FabricStockUnit,
    File,
    GalleryEntry,
    ListingImage,
    MerchantProfile,
    User,
)
from app.services import audit
from app.services.partners import merchant_public

MAX_IMAGES = 10
UPDATABLE = {"title", "description", "price_idr", "min_quantity", "quantity_increment", "material",
             "weight_gsm", "thickness_note", "usable_width_cm", "piece_length_cm", "piece_width_cm",
             "motif_orientation", "pattern_repeat_cm", "city", "province", "dispatch_days",
             "merchant_claimed_origin"}


def _check_unit_rules(unit: str, min_q: Decimal, inc: Decimal) -> None:
    if unit == "piece" and (min_q != min_q.to_integral_value() or inc != inc.to_integral_value()):
        raise AppValidationError("Piece listings must use whole-piece quantities",
                                 field="quantity_increment")


def create_listing(session: Session, merchant: MerchantProfile, user: User, data: dict) -> FabricListing:
    entry = session.get(GalleryEntry, data["entry_id"])
    if entry is None or entry.status != "published":
        raise AppValidationError("A published Gallery entry is required", field="entry_id")
    _check_unit_rules(data["selling_unit"], data["min_quantity"], data["quantity_increment"])
    data = {**data, "city": data.get("city") or merchant.city,
            "province": data.get("province") or merchant.province}
    listing = FabricListing(merchant_id=merchant.id, **data)
    session.add(listing)
    session.flush()
    audit.record(session, actor=user, action="listing.created", target_type="fabric_listing",
                 target_id=listing.id)
    return listing


def owned_listing(session: Session, merchant: MerchantProfile, listing_id: uuid.UUID) -> FabricListing:
    listing = session.get(FabricListing, listing_id)
    if listing is None or listing.merchant_id != merchant.id:
        raise NotFound("Listing not found")
    return listing


def update_listing(session: Session, user: User, listing: FabricListing, expected_revision: int,
                   changes: dict) -> FabricListing:
    if listing.status == "archived":
        raise AppValidationError("Archived listings cannot be edited", field="status")
    check_revision(expected_revision, listing.revision)
    for key, value in changes.items():
        if key in UPDATABLE and value is not None:
            setattr(listing, key, value)
    _check_unit_rules(listing.selling_unit, listing.min_quantity, listing.quantity_increment)
    listing.revision += 1
    session.flush()
    audit.record(session, actor=user, action="listing.updated", target_type="fabric_listing",
                 target_id=listing.id, metadata={"fields": sorted(changes)})
    return listing


def publish_listing(session: Session, user: User, listing: FabricListing) -> FabricListing:
    if listing.status == "published":
        return listing
    if listing.status == "archived":
        raise AppValidationError("Archived listings cannot be published", field="status")
    entry = session.get(GalleryEntry, listing.entry_id)
    if entry is None or entry.status != "published":
        raise AppValidationError("The linked Gallery entry is not published", field="entry_id")
    images = session.scalar(select(func.count()).select_from(ListingImage)
                            .where(ListingImage.listing_id == listing.id))
    if not images:
        raise AppValidationError("At least one actual fabric photo is required", field="images")
    listing.status, listing.published_at = "published", datetime.now(UTC)
    listing.revision += 1
    session.flush()
    audit.record(session, actor=user, action="listing.published", target_type="fabric_listing",
                 target_id=listing.id)
    return listing


def archive_listing(session: Session, user: User, listing: FabricListing) -> FabricListing:
    listing.status = "archived"
    listing.revision += 1
    session.flush()
    audit.record(session, actor=user, action="listing.archived", target_type="fabric_listing",
                 target_id=listing.id)
    return listing


def add_image(session: Session, user: User, listing: FabricListing, file_id: uuid.UUID,
              caption: str | None, sort_order: int) -> ListingImage:
    file = session.get(File, file_id)
    if file is None or file.deleted_at is not None or file.owner_id != user.id:
        raise NotFound("File not found")
    if file.visibility != "public":
        raise AppValidationError("Listing photos must be public files", field="file_id")
    count = session.scalar(select(func.count()).select_from(ListingImage)
                           .where(ListingImage.listing_id == listing.id))
    if count >= MAX_IMAGES:
        raise AppValidationError(f"At most {MAX_IMAGES} photos per listing", field="file_id")
    image = ListingImage(listing_id=listing.id, file_id=file_id, caption=caption,
                         sort_order=sort_order)
    session.add(image)
    session.flush()
    return image


# ---------- stock ----------

def add_stock_unit(session: Session, user: User, listing: FabricListing, length_m: Decimal | None,
                   quantity: int) -> FabricStockUnit:
    if listing.selling_unit == "meter" and length_m is None:
        raise AppValidationError("Meter listings need the continuous length of each unit",
                                 field="length_m")
    if listing.selling_unit == "piece" and length_m is not None:
        raise AppValidationError("Piece listings do not use length_m", field="length_m")
    unit = FabricStockUnit(listing_id=listing.id, length_m=length_m, quantity=quantity)
    session.add(unit)
    session.flush()
    audit.record(session, actor=user, action="stock.added", target_type="fabric_listing",
                 target_id=listing.id, metadata={"length_m": str(length_m), "quantity": quantity})
    return unit


def owned_stock_unit(session: Session, merchant: MerchantProfile, unit_id: uuid.UUID) -> FabricStockUnit:
    unit = session.get(FabricStockUnit, unit_id)
    listing = session.get(FabricListing, unit.listing_id) if unit else None
    if unit is None or listing.merchant_id != merchant.id:
        raise NotFound("Stock unit not found")
    return unit


def set_stock_quantity(session: Session, user: User, unit: FabricStockUnit, quantity: int) -> FabricStockUnit:
    unit.quantity = quantity
    session.flush()
    audit.record(session, actor=user, action="stock.updated", target_type="fabric_listing",
                 target_id=unit.listing_id, metadata={"unit_id": str(unit.id), "quantity": quantity})
    return unit


def stock_summary(session: Session, listing: FabricListing) -> dict:
    units = list(session.scalars(select(FabricStockUnit).where(
        FabricStockUnit.listing_id == listing.id, FabricStockUnit.quantity > 0)))
    if listing.selling_unit == "piece":
        pieces = sum(u.quantity for u in units)
        return {"unit": "piece", "available_pieces": pieces, "in_stock": pieces > 0}
    total = sum((u.length_m * u.quantity for u in units), Decimal(0))
    longest = max((u.length_m for u in units), default=Decimal(0))
    return {"unit": "meter", "total_length_m": total, "longest_continuous_m": longest,
            "pieces": sum(u.quantity for u in units), "in_stock": total > 0}


# ---------- views ----------

def missing_for_custom(listing: FabricListing) -> list[str]:
    missing = []
    if not listing.material:
        missing.append("material")
    if listing.selling_unit == "meter" and not listing.usable_width_cm:
        missing.append("usable_width_cm")
    if listing.selling_unit == "piece" and not (listing.piece_length_cm and listing.piece_width_cm):
        missing.append("piece_dimensions")
    return missing


def images_out(session: Session, listing_id: uuid.UUID) -> list[dict]:
    rows = session.scalars(select(ListingImage).where(ListingImage.listing_id == listing_id)
                           .order_by(ListingImage.sort_order, ListingImage.id))
    return [{"url": f"/api/v1/files/{r.file_id}", "caption": r.caption} for r in rows]


def listing_out(session: Session, listing: FabricListing, *, include_merchant: bool = True) -> dict:
    missing = missing_for_custom(listing)
    out = {
        "id": listing.id, "entry_id": listing.entry_id, "title": listing.title,
        "description": listing.description, "material": listing.material or "tidak diketahui",
        "weight_gsm": listing.weight_gsm, "thickness_note": listing.thickness_note,
        "usable_width_cm": listing.usable_width_cm, "selling_unit": listing.selling_unit,
        "price_idr": listing.price_idr, "min_quantity": listing.min_quantity,
        "quantity_increment": listing.quantity_increment,
        "piece_length_cm": listing.piece_length_cm, "piece_width_cm": listing.piece_width_cm,
        "motif_orientation": listing.motif_orientation,
        "pattern_repeat_cm": listing.pattern_repeat_cm, "city": listing.city,
        "province": listing.province, "dispatch_days": listing.dispatch_days,
        "origin": {"visual_match": listing.visual_match,
                   "merchant_claimed_origin": listing.merchant_claimed_origin,
                   "curator_verified_origin": listing.curator_verified_origin},
        "status": listing.status, "revision": listing.revision,
        "images": images_out(session, listing.id), "stock": stock_summary(session, listing),
        "custom_order_ready": not missing, "missing_for_custom": missing,
    }
    if include_merchant:
        merchant = session.get(MerchantProfile, listing.merchant_id)
        out["merchant"] = merchant_public(merchant)
    return out


def public_listing(session: Session, listing_id: uuid.UUID) -> FabricListing:
    listing = session.get(FabricListing, listing_id)
    if listing is not None and listing.status == "published":
        merchant = session.get(MerchantProfile, listing.merchant_id)
        entry = session.get(GalleryEntry, listing.entry_id)
        if merchant.status == "active" and entry.status == "published":
            return listing
    raise NotFound("Listing not found")


def listings_for_entry(session: Session, entry: GalleryEntry, *, city: str | None,
                       max_price: int | None, sort: str, limit: int) -> list[FabricListing]:
    stmt = (select(FabricListing).join(MerchantProfile, MerchantProfile.id == FabricListing.merchant_id)
            .where(FabricListing.entry_id == entry.id, FabricListing.status == "published",
                   MerchantProfile.status == "active"))
    if city:
        stmt = stmt.where(func.lower(FabricListing.city) == city.lower())
    if max_price:
        stmt = stmt.where(FabricListing.price_idr <= max_price)
    stmt = stmt.order_by(FabricListing.price_idr if sort == "price_asc" else FabricListing.created_at.desc())
    return list(session.scalars(stmt.limit(limit)))


def entry_availability(session: Session, entry_id: uuid.UUID) -> dict:
    row = session.execute(
        select(func.count(), func.min(FabricListing.price_idr))
        .join(MerchantProfile, MerchantProfile.id == FabricListing.merchant_id)
        .where(FabricListing.entry_id == entry_id, FabricListing.status == "published",
               MerchantProfile.status == "active")).one()
    return {"listing_count": row[0], "min_price_idr": row[1]}


def require_owner_user(listing: FabricListing, merchant: MerchantProfile) -> None:
    if listing.merchant_id != merchant.id:
        raise Forbidden()
