import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.core.errors import InvalidTransition, NotFound
from app.core.pagination import paginate
from app.core.responses import ok
from app.db.base import get_session
from app.models import FabricListing, FabricStockUnit, ListingImage, User
from app.schemas.listing import (
    ListingCreate,
    ListingImageIn,
    ListingUpdate,
    StockUnitIn,
    StockUnitUpdate,
)
from app.services import audit
from app.services import gallery as gallery_svc
from app.services import listings as svc
from app.services.partners import active_merchant

router = APIRouter(tags=["listings"])


def _unit_out(u: FabricStockUnit) -> dict:
    return {"id": u.id, "listing_id": u.listing_id, "length_m": u.length_m, "quantity": u.quantity}


# ----- public -----

@router.get("/gallery/{ref}/listings")
def entry_listings(ref: str, city: str | None = Query(default=None),
                   max_price: int | None = Query(default=None, gt=0),
                   variant_id: uuid.UUID | None = Query(default=None),
                   sort: str = Query(default="price_asc", pattern="^(price_asc|newest)$"),
                   limit: int = Query(default=20, ge=1, le=50),
                   session: Session = Depends(get_session)):
    entry = gallery_svc.get_published_by_ref(session, ref)
    rows = svc.listings_for_entry(session, entry, city=city, max_price=max_price, sort=sort,
                                  limit=limit, variant_id=variant_id)
    return ok({"gallery_entry": gallery_svc.brief(entry),
               "items": [svc.listing_out(session, r) for r in rows],
               "notice": "Gallery menjelaskan budaya; setiap listing adalah barang nyata milik "
                         "merchant dengan spesifikasi dan stoknya sendiri."})


@router.get("/listings/{listing_id}")
def listing_detail(listing_id: uuid.UUID, session: Session = Depends(get_session)):
    listing = svc.public_listing(session, listing_id)
    entry = gallery_svc.get_entry(session, listing.entry_id)
    return ok({**svc.listing_out(session, listing), "gallery_entry": gallery_svc.brief(entry)})


# ----- merchant -----

@router.post("/listings", status_code=201)
def create_listing(body: ListingCreate, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    merchant = active_merchant(session, user)
    listing = svc.create_listing(session, merchant, user, body.model_dump())
    session.commit()
    return ok(svc.listing_out(session, listing, include_merchant=False))


@router.get("/merchant/listings")
def my_listings(limit: int = Query(default=20, ge=1, le=100), cursor: str | None = Query(default=None),
                user: User = Depends(current_user), session: Session = Depends(get_session)):
    merchant = active_merchant(session, user)
    stmt = select(FabricListing).where(FabricListing.merchant_id == merchant.id)
    page = paginate(session, FabricListing, stmt, limit=limit, cursor=cursor)
    return ok({"items": [svc.listing_out(session, r, include_merchant=False) for r in page["items"]],
               "next_cursor": page["next_cursor"]})


@router.get("/merchant/listings/{listing_id}")
def my_listing(listing_id: uuid.UUID, user: User = Depends(current_user),
               session: Session = Depends(get_session)):
    merchant = active_merchant(session, user)
    return ok(svc.listing_out(session, svc.owned_listing(session, merchant, listing_id),
                              include_merchant=False))


@router.patch("/listings/{listing_id}")
def update_listing(listing_id: uuid.UUID, body: ListingUpdate, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    merchant = active_merchant(session, user)
    listing = svc.owned_listing(session, merchant, listing_id)
    changes = body.model_dump(exclude={"expected_revision"}, exclude_unset=True)
    svc.update_listing(session, user, listing, body.expected_revision, changes)
    session.commit()
    return ok(svc.listing_out(session, listing, include_merchant=False))


@router.post("/listings/{listing_id}/publish")
def publish_listing(listing_id: uuid.UUID, user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
    merchant = active_merchant(session, user)
    listing = svc.publish_listing(session, user, svc.owned_listing(session, merchant, listing_id))
    session.commit()
    return ok(svc.listing_out(session, listing, include_merchant=False))


@router.post("/listings/{listing_id}/archive")
def archive_listing(listing_id: uuid.UUID, user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
    merchant = active_merchant(session, user)
    listing = svc.archive_listing(session, user, svc.owned_listing(session, merchant, listing_id))
    session.commit()
    return ok(svc.listing_out(session, listing, include_merchant=False))


@router.post("/listings/{listing_id}/images", status_code=201)
def add_image(listing_id: uuid.UUID, body: ListingImageIn, user: User = Depends(current_user),
              session: Session = Depends(get_session)):
    merchant = active_merchant(session, user)
    listing = svc.owned_listing(session, merchant, listing_id)
    image = svc.add_image(session, user, listing, body.file_id, body.caption, body.sort_order)
    session.commit()
    return ok({"id": image.id, "url": f"/api/v1/files/{image.file_id}"})


@router.delete("/listings/{listing_id}/images/{image_id}")
def remove_image(listing_id: uuid.UUID, image_id: uuid.UUID, user: User = Depends(current_user),
                 session: Session = Depends(get_session)):
    merchant = active_merchant(session, user)
    listing = svc.owned_listing(session, merchant, listing_id)
    image = session.get(ListingImage, image_id)
    if image is None or image.listing_id != listing.id:
        raise NotFound("Listing image not found")
    if listing.status == "published":
        count = session.scalar(select(func.count()).select_from(ListingImage)
                               .where(ListingImage.listing_id == listing.id))
        if count <= 1:
            raise InvalidTransition("Listing terbit harus memiliki setidaknya satu foto")
    session.delete(image)
    session.flush()
    audit.record(session, actor=user, action="listing.image_removed", target_type="fabric_listing",
                 target_id=listing.id, metadata={"image_id": str(image_id), "file_kept": True})
    session.commit()
    return ok({"removed": str(image_id), "file_kept": True})


@router.post("/listings/{listing_id}/stock-units", status_code=201)
def add_stock_unit(listing_id: uuid.UUID, body: StockUnitIn, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    merchant = active_merchant(session, user)
    listing = svc.owned_listing(session, merchant, listing_id)
    unit = svc.add_stock_unit(session, user, listing, body.length_m, body.quantity)
    session.commit()
    return ok(_unit_out(unit))


@router.patch("/stock-units/{unit_id}")
def update_stock_unit(unit_id: uuid.UUID, body: StockUnitUpdate, user: User = Depends(current_user),
                      session: Session = Depends(get_session)):
    merchant = active_merchant(session, user)
    unit = svc.set_stock_quantity(session, user, svc.owned_stock_unit(session, merchant, unit_id),
                                  body.quantity)
    session.commit()
    return ok(_unit_out(unit))


@router.get("/merchant/stock")
def my_stock(user: User = Depends(current_user), session: Session = Depends(get_session)):
    merchant = active_merchant(session, user)
    listings = session.scalars(select(FabricListing).where(FabricListing.merchant_id == merchant.id))
    out = []
    for listing in listings:
        units = session.scalars(select(FabricStockUnit).where(FabricStockUnit.listing_id == listing.id))
        out.append({"listing_id": listing.id, "title": listing.title, "summary":
                    svc.stock_summary(session, listing), "units": [_unit_out(u) for u in units]})
    return ok(out)
