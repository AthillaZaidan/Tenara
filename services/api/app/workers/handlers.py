"""Job handlers for the AI worker. Import this module (the worker does) to register them.

Failures that retrying cannot fix raise PermanentJobError so they are reported honestly, never faked.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ml.vision import body_measure, render
from app.ml.vision.body_measure import MeasurementFailure
from app.ml.vision.pose import get_pose_detector
from app.models import (
    BodyPhoto,
    Customization,
    DesignRevision,
    FabricListing,
    File,
    Job,
    ListingImage,
    MeasurementSet,
    MeasurementValue,
    Preview,
)
from app.services import jobs, photos
from app.services.files import create_file
from app.services.jobs import PermanentJobError
from app.services.storage import get_storage

PRODUCT_METHOD = "pillow_flat_composite_v1"
ONBODY_METHOD = "pose_landmark_composite_v1"
VISUAL_LABEL = "Ilustrasi konseptual; bukan simulasi kecocokan, jatuhnya kain, atau pola potong."


def _storage():
    return get_storage()


def handle_measurement_estimate(session: Session, job: Job) -> dict:
    data = job.input
    photo = session.get(BodyPhoto, uuid.UUID(data["photo_id"]))
    if photo is None or photo.owner_id != job.owner_id or photo.status != "stored":
        raise PermanentJobError("Foto tidak tersedia (mungkin sudah dihapus atau masa simpan habis)")
    detector = get_pose_detector()
    if detector is None:
        raise PermanentJobError("Model pose belum terpasang di server; isi ukuran secara manual")
    image = photos.load_image(session, _storage(), photo)
    try:
        estimate = body_measure.estimate(detector.detect(image), float(data["height_cm"]), image.size)
    except MeasurementFailure as exc:
        raise PermanentJobError(str(exc)) from exc
    mset = MeasurementSet(owner_id=job.owner_id, height_cm=data["height_cm"])
    session.add(mset)
    session.flush()
    for key, item in estimate["values"].items():
        session.add(MeasurementValue(
            set_id=mset.id, key=key, value_cm=item["value_cm"], source=item["source"],
            quality_flag=item["quality_flag"], model_version=estimate["model_version"],
            history=[]))
    job.model_version = estimate["model_version"]
    session.flush()
    return {"measurement_set_id": str(mset.id), "scale_basis": estimate["scale_basis"],
            "supported": [k for k, v in estimate["values"].items() if v["source"] == "estimated"],
            "manual_required": [k for k, v in estimate["values"].items()
                                if v["source"] == "manual_required"],
            "warnings": estimate["warnings"]}


def _design(session: Session, preview: Preview):
    cust = session.get(Customization, preview.customization_id)
    revision = session.scalar(select(DesignRevision).where(
        DesignRevision.customization_id == cust.id, DesignRevision.revision == preview.design_revision))
    listing = session.get(FabricListing, cust.listing_id)
    return cust, revision, listing


def _texture(session: Session, listing: FabricListing):
    image = session.scalar(select(ListingImage).where(ListingImage.listing_id == listing.id)
                           .order_by(ListingImage.sort_order, ListingImage.id).limit(1))
    file = session.get(File, image.file_id) if image else None
    if file is None or file.deleted_at is not None:
        raise PermanentJobError("Listing tidak memiliki foto kain untuk dipakai sebagai tekstur")
    return render.load_texture(_storage().open(file.storage_key))


def _save(session: Session, preview: Preview, cust: Customization, image, method: str,
          warnings: list[str], job: Job) -> dict:
    stored = create_file(session, _storage(), owner_id=cust.buyer_id, kind="preview",
                         data=render.to_png(image), content_type="image/png")
    preview.file_id, preview.method = stored.id, method
    preview.warnings = [VISUAL_LABEL, *warnings]
    preview.status = "completed_with_warnings" if warnings else "completed"
    job.model_version = method
    session.flush()
    return {"preview_id": str(preview.id), "warnings": warnings}


def handle_product_preview(session: Session, job: Job) -> dict:
    preview = session.get(Preview, uuid.UUID(job.input["preview_id"]))
    cust, revision, listing = _design(session, preview)
    rendered = render.render_garment(cust.template_code, revision.state, _texture(session, listing))
    return _save(session, preview, cust, rendered.image, PRODUCT_METHOD, rendered.warnings, job)


def handle_on_body_preview(session: Session, job: Job) -> dict:
    preview = session.get(Preview, uuid.UUID(job.input["preview_id"]))
    photo = session.get(BodyPhoto, uuid.UUID(job.input["photo_id"]))
    if photo is None or photo.owner_id != job.owner_id or photo.status != "stored":
        raise PermanentJobError("Foto tidak tersedia (mungkin sudah dihapus atau masa simpan habis)")
    detector = get_pose_detector()
    if detector is None:
        raise PermanentJobError("Model pose belum terpasang; hanya pratinjau produk datar yang tersedia")
    cust, revision, listing = _design(session, preview)
    image = photos.load_image(session, _storage(), photo)
    pose = detector.detect(image)
    if pose.pose_count != 1:
        raise PermanentJobError("Tidak terdeteksi tepat satu orang pada foto; ambil ulang fotonya")
    for name in ("l_shoulder", "r_shoulder"):
        if pose.landmarks[name].visibility < body_measure.MIN_VISIBILITY:
            raise PermanentJobError("Bahu tidak terlihat jelas; ambil ulang fotonya")
    rendered = render.render_garment(cust.template_code, revision.state, _texture(session, listing))
    composite = render.compose_on_body(image, pose, rendered.image)
    return _save(session, preview, cust, composite, ONBODY_METHOD, rendered.warnings, job)


jobs.register_handler("measurement.estimate", handle_measurement_estimate)
jobs.register_handler("preview.product", handle_product_preview)
jobs.register_handler("preview.on_body", handle_on_body_preview)
