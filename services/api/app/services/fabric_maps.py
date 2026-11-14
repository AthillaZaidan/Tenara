"""Fabric maps: request (any signed-in user, one per listing photo), read (public), confirm (merchant)."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppValidationError, ServiceUnavailable
from app.core.revision import check_revision
from app.ml.vision import fabric_map
from app.models import FabricListing, FabricMap, Job, ListingImage, User
from app.services import audit, jobs

JOB = "fabric.map"
ESTIMATE_LABEL = ("Perkiraan AI dari foto kain; penjual belum mengonfirmasi. Letak motif bisa meleset, "
                  "penjahit memastikannya pada kain asli.")
CONFIRMED_LABEL = "Dikonfirmasi penjual. Penjahit tetap memastikan letak motif pada kain asli."


def first_image(session: Session, listing: FabricListing) -> ListingImage | None:
    return session.scalar(select(ListingImage).where(ListingImage.listing_id == listing.id)
                          .order_by(ListingImage.sort_order, ListingImage.id).limit(1))


def current_map(session: Session, listing: FabricListing) -> FabricMap | None:
    """The map of the listing's current first photo; a map of an older photo does not count."""
    fmap = session.scalar(select(FabricMap).where(FabricMap.listing_id == listing.id))
    image = first_image(session, listing)
    if fmap is None or image is None or fmap.file_id != image.file_id:
        return None
    return fmap


def request_map(session: Session, user: User, listing: FabricListing) -> FabricMap:
    """Start mapping the first photo unless a live map of it exists (idempotent)."""
    fmap = current_map(session, listing)
    job = session.get(Job, fmap.job_id) if fmap and fmap.job_id else None
    if fmap is not None and fmap.status != "failed" and not (job and job.status == "failed"):
        return fmap
    image = first_image(session, listing)
    if image is None:
        raise AppValidationError("Listing belum punya foto kain", field="listing_id")
    if not fabric_map.available():
        raise ServiceUnavailable("Model visi belum dikonfigurasi; peta motif kain tidak tersedia")
    fmap = session.scalar(select(FabricMap).where(FabricMap.listing_id == listing.id))
    if fmap is None:
        fmap = FabricMap(listing_id=listing.id, file_id=image.file_id)
        session.add(fmap)
    fmap.file_id, fmap.regions, fmap.status, fmap.method = image.file_id, [], "pending", None
    fmap.confirmed_by = fmap.confirmed_at = None
    session.flush()
    fmap.job_id = jobs.enqueue(session, JOB, user.id, {"map_id": str(fmap.id)},
                               subject_type="listing", subject_id=listing.id).id
    session.flush()
    return fmap


def map_out(session: Session, fmap: FabricMap | None) -> dict | None:
    if fmap is None:
        return None
    job = session.get(Job, fmap.job_id) if fmap.job_id else None
    status, error = fmap.status, None
    if fmap.status == "pending" and job is not None and job.status == "failed":
        status, error = "failed", job.error
    return {"id": fmap.id, "listing_id": fmap.listing_id, "status": status, "error": error,
            "revision": fmap.revision, "regions": fmap.regions, "method": fmap.method,
            "photo_url": f"/api/v1/files/{fmap.file_id}", "confirmed_at": fmap.confirmed_at,
            "job_id": fmap.job_id,
            "label": CONFIRMED_LABEL if status == "confirmed" else ESTIMATE_LABEL}


def _checked_regions(regions: list) -> list[dict]:
    out, ids = [], set()
    for i, r in enumerate(regions):
        where = f"regions.{i}"
        if not isinstance(r, dict):
            raise AppValidationError("Region harus berupa objek", field=where)
        rid, kind, label, box = r.get("id"), r.get("kind"), r.get("label"), r.get("box")
        if not isinstance(rid, str) or not rid or rid in ids:
            raise AppValidationError("id region wajib dan unik", field=f"{where}.id")
        if kind not in ("zone", "motif"):
            raise AppValidationError("kind harus zone atau motif", field=f"{where}.kind")
        if not isinstance(label, str) or not label.strip():
            raise AppValidationError("label wajib", field=f"{where}.label")
        try:
            x0, y0, x1, y1 = (float(v) for v in box)
        except (TypeError, ValueError):
            raise AppValidationError("box harus [x0, y0, x1, y1] dalam 0..1", field=f"{where}.box") from None
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise AppValidationError("box harus [x0, y0, x1, y1] dalam 0..1", field=f"{where}.box")
        repeats = r.get("repeats")
        if repeats is not None and (not isinstance(repeats, int) or repeats < 1):
            raise AppValidationError("repeats harus bilangan bulat >= 1", field=f"{where}.repeats")
        ids.add(rid)
        out.append({"id": rid, "kind": kind, "label": fabric_map.label_key(label)[:40],
                    "box": [round(v, 3) for v in (x0, y0, x1, y1)], "repeats": repeats})
    return out


def confirm(session: Session, user: User, listing: FabricListing, expected_revision: int,
            regions: list | None) -> FabricMap:
    """The merchant accepts the map as it is, or with corrected regions."""
    fmap = current_map(session, listing)
    if fmap is None or fmap.status not in ("estimated", "confirmed"):
        raise AppValidationError("Belum ada peta kain yang selesai untuk dikonfirmasi", field="listing_id")
    check_revision(expected_revision, fmap.revision)
    if regions is not None:
        fmap.regions = _checked_regions(regions)
    fmap.status, fmap.confirmed_by, fmap.confirmed_at = "confirmed", user.id, datetime.now(UTC)
    fmap.revision += 1
    session.flush()
    audit.record(session, actor=user, action="fabric_map.confirmed", target_type="listing",
                 target_id=listing.id, metadata={"regions": len(fmap.regions), "corrected": regions is not None})
    return fmap


def region(fmap: FabricMap | None, region_id: str) -> dict | None:
    return next((r for r in (fmap.regions if fmap else []) if r["id"] == region_id), None)


def by_id(session: Session, map_id: str) -> FabricMap | None:
    return session.get(FabricMap, uuid.UUID(map_id))
