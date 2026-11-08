import uuid

from fastapi import APIRouter, Depends, Form, UploadFile
from fastapi import File as FormFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import current_user, require_role
from app.core.errors import AppValidationError, NotFound
from app.core.ownership import get_owned_or_404
from app.core.responses import ok
from app.db.base import get_session
from app.ml.text.embedding import Embedder, get_embedder
from app.ml.vision import vlm
from app.ml.vision.vlm import VLMClient, get_vlm
from app.models import (
    BodyPhoto,
    FabricListing,
    File,
    GalleryEntry,
    Job,
    ListingImage,
    MeasurementSet,
    User,
)
from app.schemas.ai import (
    AnalyzeIn,
    ConsentIn,
    EstimateIn,
    MotifReviewIn,
    TryOnIn,
    VerifyOriginIn,
)
from app.services import audit, jobs, photos
from app.services import customization as cust_svc
from app.services import listings as listings_svc
from app.services import measurements as meas_svc
from app.services.partners import active_merchant
from app.services.storage import Storage, get_storage

router = APIRouter(tags=["ai"])


# ----- photo consent + intake (private by default) -----

@router.get("/photo-consent-notice")
def consent_notice():
    return ok({"version": photos.NOTICE_VERSION, "text": photos.CONSENT_TEXT,
               "default_retention_minutes": settings.photo_default_retention_minutes,
               "max_retention_days": settings.photo_max_retention_days,
               "guidance": ["Seluruh badan, satu orang, menghadap depan",
                            "Pakaian pas badan, bahu dan pinggul terlihat jelas",
                            "Foto dari depan setinggi pinggang, cahaya cukup",
                            "Masukkan tinggi badan dalam cm sebagai skala"]})


@router.post("/photo-consents", status_code=201)
def give_consent(body: ConsentIn, user: User = Depends(current_user),
                 session: Session = Depends(get_session)):
    consent = photos.create_consent(session, user, retention_minutes=body.retention_minutes,
                                    share_original=body.share_original_with_tailor,
                                    allow_training=body.allow_training_use)
    session.commit()
    return ok({"id": consent.id, "retention_minutes": consent.retention_minutes,
               "notice_version": consent.notice_version})


@router.post("/photo-consents/{consent_id}/revoke")
def revoke_consent(consent_id: uuid.UUID, user: User = Depends(current_user),
                   session: Session = Depends(get_session),
                   storage: Storage = Depends(get_storage)):
    consent = photos.owned_consent(session, user, consent_id)
    deleted = photos.revoke_consent(session, storage, user, consent)
    session.commit()
    return ok({"revoked": True, "photos_deleted": deleted})


@router.post("/body-photos", status_code=201)
async def upload_body_photo(file: UploadFile = FormFile(...), consent_id: uuid.UUID = Form(...),
                            user: User = Depends(current_user),
                            session: Session = Depends(get_session),
                            storage: Storage = Depends(get_storage)):
    data = await file.read(settings.photo_max_bytes + 1)
    photo = photos.upload_photo(session, storage, user, data, file.content_type or "", consent_id)
    session.commit()
    return ok(photos.photo_out(photo))


@router.get("/body-photos")
def list_body_photos(user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = session.scalars(select(BodyPhoto).where(BodyPhoto.owner_id == user.id,
                                                   BodyPhoto.status == "stored")
                           .order_by(BodyPhoto.created_at.desc()))
    return ok([photos.photo_out(p) for p in rows])


@router.delete("/body-photos/{photo_id}")
def delete_body_photo(photo_id: uuid.UUID, user: User = Depends(current_user),
                      session: Session = Depends(get_session),
                      storage: Storage = Depends(get_storage)):
    photo = photos.owned_photo(session, user, photo_id)
    photos.delete_photo(session, storage, photo, user)
    session.commit()
    return ok({"deleted": str(photo_id), "kept": ["measurement sets", "approved order specifications"]})


# ----- automatic measurement (async) -----

@router.post("/body-measurements/estimate", status_code=202)
def estimate_measurements(body: EstimateIn, user: User = Depends(current_user),
                          session: Session = Depends(get_session)):
    photos.owned_photo(session, user, body.body_photo_id)
    if body.customization_id:
        cust_svc.owned_customization(session, user, body.customization_id)
    job = jobs.enqueue(session, "measurement.estimate", user.id,
                       {"photo_id": str(body.body_photo_id), "height_cm": body.height_cm})
    session.commit()
    return ok({"job_id": job.id, "status": job.status})


@router.get("/body-measurements/{job_id}")
def measurement_job(job_id: uuid.UUID, user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
    job = get_owned_or_404(session, Job, job_id, user)
    if job.kind != "measurement.estimate":
        raise NotFound("Job not found")
    out = {"job_id": job.id, "status": job.status, "error": job.error, "output": job.output,
           "model_version": job.model_version, "measurement_set": None}
    if job.output and job.output.get("measurement_set_id"):
        mset = session.get(MeasurementSet, uuid.UUID(job.output["measurement_set_id"]))
        out["measurement_set"] = meas_svc.set_out(session, mset)
    return ok(out)


# ----- photo try-on -----

@router.post("/customizations/{cust_id}/photo-try-ons", status_code=202)
def photo_try_on(cust_id: uuid.UUID, body: TryOnIn, user: User = Depends(current_user),
                 session: Session = Depends(get_session)):
    cust = cust_svc.owned_customization(session, user, cust_id)
    photos.owned_photo(session, user, body.body_photo_id)
    preview = cust_svc.request_on_body_preview(session, user, cust, body.body_photo_id)
    session.commit()
    return ok(cust_svc.preview_out(session, preview))


# ----- seller-side visual analysis -----

@router.post("/vision/analyze")
def analyze_fabric(body: AnalyzeIn, user: User = Depends(current_user),
                   session: Session = Depends(get_session),
                   storage: Storage = Depends(get_storage),
                   client: VLMClient | None = Depends(get_vlm),
                   embedder: Embedder | None = Depends(get_embedder)):
    merchant = active_merchant(session, user)
    listing = listings_svc.owned_listing(session, merchant, body.listing_id)
    file_id = body.file_id
    if file_id is None:
        first = session.scalar(select(ListingImage).where(ListingImage.listing_id == listing.id)
                               .order_by(ListingImage.sort_order, ListingImage.id).limit(1))
        file_id = first.file_id if first else None
    file = session.get(File, file_id) if file_id else None
    if file is None or file.owner_id != user.id or file.deleted_at is not None:
        raise AppValidationError("Foto kain tidak ditemukan", field="file_id")
    row = vlm.run_analysis(session, user, listing, file.id, storage.open(file.storage_key),
                           file.content_type, client, embedder)
    session.commit()
    return ok(vlm.analysis_out(row))


@router.patch("/listings/{listing_id}/motif-review")
def motif_review(listing_id: uuid.UUID, body: MotifReviewIn, user: User = Depends(current_user),
                 session: Session = Depends(get_session)):
    merchant = active_merchant(session, user)
    listing = listings_svc.owned_listing(session, merchant, listing_id)
    if not listing.visual_match:
        raise AppValidationError("Belum ada saran visual untuk ditinjau", field="decision")
    review = {"decision": body.decision, "reviewed_by": str(user.id)}
    if body.decision == "correct":
        entry = session.get(GalleryEntry, body.entry_id) if body.entry_id else None
        if entry is None or entry.status != "published":
            raise AppValidationError("Pilih entri Gallery yang terbit", field="entry_id")
        review["entry_id"] = str(entry.id)
    updated = dict(listing.visual_match)
    updated["review"] = review
    updated["needs_merchant_review"] = False
    listing.visual_match = updated
    if body.merchant_claimed_origin is not None:
        listing.merchant_claimed_origin = body.merchant_claimed_origin  # a claim, not a verification
    session.flush()
    audit.record(session, actor=user, action=f"listing.motif_{body.decision}",
                 target_type="fabric_listing", target_id=listing.id)
    session.commit()
    return ok(listings_svc.listing_out(session, listing, include_merchant=False))


@router.post("/admin/listings/{listing_id}/verify-origin")
def verify_origin(listing_id: uuid.UUID, body: VerifyOriginIn,
                  user: User = Depends(require_role("admin")),
                  session: Session = Depends(get_session)):
    listing = session.get(FabricListing, listing_id)
    if listing is None:
        raise NotFound("Listing not found")
    listing.curator_verified_origin = body.text
    session.flush()
    audit.record(session, actor=user, action="listing.origin_verified",
                 target_type="fabric_listing", target_id=listing.id)
    session.commit()
    return ok(listings_svc.listing_out(session, listing, include_merchant=False))


