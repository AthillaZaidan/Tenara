"""Job handlers for the AI worker. Import this module (the worker does) to register them.

Failures that retrying cannot fix raise PermanentJobError so they are reported honestly, never faked.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppValidationError, ServiceUnavailable
from app.ml.text import product_story
from app.ml.text.embedding import get_embedder
from app.ml.text.story_gen import get_story_llm
from app.ml.vision import avatar, body3d, body_measure, render
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
    TemplateVersion,
    User,
)
from app.services import jobs, photos
from app.services.files import create_file
from app.services.jobs import PermanentJobError
from app.services.measurements import DIMENSION_RANGES
from app.services.storage import get_storage

PRODUCT_METHOD = "pillow_flat_composite_v1"
ONBODY_METHOD = "pose_landmark_composite_v1"
VISUAL_LABEL = "Ilustrasi konseptual; bukan simulasi kecocokan, jatuhnya kain, atau pola potong."


def _storage():
    return get_storage()


def _owned_stored_photo(session: Session, job: Job, photo_id: str) -> BodyPhoto:
    photo = session.get(BodyPhoto, uuid.UUID(photo_id))
    if photo is None or photo.owner_id != job.owner_id or photo.status != "stored":
        raise PermanentJobError("Foto tidak tersedia (mungkin sudah dihapus atau masa simpan habis)")
    return photo


def _body_model(gender: str):
    return body3d.get_body_model(gender)


def _estimate_two_views(session: Session, job: Job, front: BodyPhoto, side: BodyPhoto, body, detector) -> dict:
    """SMPL-X fitted to a front and a side photo: all seven dimensions, plus where to draw them."""
    data = job.input
    result = body3d.estimate_two_views(body, detector, photos.load_image(session, _storage(), front),
                                       photos.load_image(session, _storage(), side), float(data["height_cm"]))
    if result["problems"]:
        raise PermanentJobError(" ".join(result["problems"]))
    model_version = f"{body3d.MODEL_VERSION}+{detector.model_version}"
    mset = MeasurementSet(owner_id=job.owner_id, height_cm=data["height_cm"])
    session.add(mset)
    session.flush()
    warnings = ["buyer_review_required",
                "loose_clothing: baju longgar ikut terukur sehingga lingkar bisa lebih besar; cek dengan meteran"]
    supported, manual = [], []
    for key, (lo, hi) in DIMENSION_RANGES.items():
        value = result["values"].get(key)
        if value is not None and lo <= value <= hi:
            source, flag, cm = "estimated", "review_required", value
            supported.append(key)
        else:
            source, flag, cm = "manual_required", "implausible" if value is not None else "unsupported", None
            manual.append(key)
            if value is not None:
                warnings.append(f"{key}_implausible: hasil di luar rentang wajar, isi manual")
        session.add(MeasurementValue(set_id=mset.id, key=key, value_cm=cm, source=source, quality_flag=flag,
                                     model_version=model_version, history=[]))
    job.model_version = model_version
    session.flush()
    visual = {kind: {"photo_id": str(photo.id), **result["visual"][kind]}
              for kind, photo in (("front", front), ("side", side))}
    return {"measurement_set_id": str(mset.id), "method": "smplx_two_view", "scale_basis": "full_height",
            "supported": supported, "manual_required": manual, "warnings": warnings, "visual": visual,
            "fit_loss": result["fit_loss"]}


def handle_measurement_estimate(session: Session, job: Job) -> dict:
    data = job.input
    photo = _owned_stored_photo(session, job, data["photo_id"])
    detector = get_pose_detector()
    if detector is None:
        raise PermanentJobError("Model pose belum terpasang di server; isi ukuran secara manual")
    fallback_warnings = []
    if data.get("side_photo_id"):
        side = _owned_stored_photo(session, job, data["side_photo_id"])
        body = _body_model(data.get("gender") or "neutral")
        if body is not None:
            return _estimate_two_views(session, job, photo, side, body, detector)
        fallback_warnings.append("smplx_unavailable: model tubuh 3D belum terpasang di server; hanya ukuran dari "
                                 "foto depan yang diperkirakan")
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
            "method": "pose_front_only", "warnings": estimate["warnings"] + fallback_warnings}


def _design(session: Session, preview: Preview):
    cust = session.get(Customization, preview.customization_id)
    revision = session.scalar(select(DesignRevision).where(
        DesignRevision.customization_id == cust.id, DesignRevision.revision == preview.design_revision))
    listing = session.get(FabricListing, cust.listing_id)
    return cust, revision, listing


def _fabric_photo(session: Session, listing: FabricListing) -> bytes:
    image = session.scalar(select(ListingImage).where(ListingImage.listing_id == listing.id)
                           .order_by(ListingImage.sort_order, ListingImage.id).limit(1))
    file = session.get(File, image.file_id) if image else None
    if file is None or file.deleted_at is not None:
        raise PermanentJobError("Listing tidak memiliki foto kain untuk dipakai sebagai tekstur")
    return _storage().open(file.storage_key)


def _texture(session: Session, listing: FabricListing):
    return render.load_texture(_fabric_photo(session, listing))


def _save(session: Session, preview: Preview, cust: Customization, image, method: str,
          warnings: list[str], job: Job, *, data: bytes | None = None, content_type: str = "image/png",
          label: str = VISUAL_LABEL) -> dict:
    stored = create_file(session, _storage(), owner_id=cust.buyer_id, kind="preview",
                         data=render.to_png(image) if data is None else data, content_type=content_type)
    preview.file_id, preview.method = stored.id, method
    preview.warnings = [label, *warnings]
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


AVATAR_LABEL = ("Avatar dibentuk dari angka ukuran saja (tanpa foto). Baju digambar mengikuti badan dengan "
                "kelonggaran template; bukan simulasi jatuhnya kain atau pola potong.")


def handle_avatar_preview(session: Session, job: Job) -> dict:
    """The buyer's body rebuilt from their measurements (SMPL-X) wearing the design, as a GLB."""
    preview = session.get(Preview, uuid.UUID(job.input["preview_id"]))
    mset = session.get(MeasurementSet, preview.measurement_set_id) if preview.measurement_set_id else None
    if mset is None or mset.owner_id != job.owner_id or mset.revision != preview.measurement_revision:
        raise PermanentJobError("Ukuran badan sudah berubah atau dihapus; buat avatar lagi")
    body = _body_model(job.input.get("gender") or "neutral")
    if body is None:
        raise PermanentJobError("Model tubuh 3D (SMPL-X) belum terpasang di server; avatar 3D tidak tersedia")
    cust, revision, listing = _design(session, preview)
    values = {v.key: float(v.value_cm) for v in session.scalars(
        select(MeasurementValue).where(MeasurementValue.set_id == mset.id)) if v.value_cm is not None}
    rules = session.get(TemplateVersion, cust.template_version_id).definition["material_rules"]
    result = avatar.build(body, cust.template_code, revision.state, float(rules["ease_cm"]),
                          float(mset.height_cm), values, avatar.fabric_texture(_fabric_photo(session, listing)))
    out = _save(session, preview, cust, None, avatar.METHOD, result.warnings, job, data=result.glb,
                content_type="model/gltf-binary", label=AVATAR_LABEL)
    return {**out, "fitted": result.fitted}


def _story_llm():
    return get_story_llm()


def _embedder():
    return get_embedder()


def handle_story_generate(session: Session, job: Job) -> dict:
    """Writer + critic story for a listing; long prose takes 30-60 s, so it runs here, not in the request."""
    listing = session.get(FabricListing, uuid.UUID(job.input["listing_id"]))
    user = session.get(User, job.owner_id)
    if listing is None or user is None:
        raise PermanentJobError("Listing tidak ditemukan")
    llm = _story_llm()
    try:
        story = product_story.generate(session, user, listing, llm, _embedder())
    except AppValidationError as exc:
        raise PermanentJobError(exc.message) from exc
    except ServiceUnavailable as exc:
        if llm is None:
            raise PermanentJobError(exc.message) from exc
        raise RuntimeError(exc.message) from exc  # provider hiccup: the job queue retries
    return {"story_id": str(story.id)}


jobs.register_handler("measurement.estimate", handle_measurement_estimate)
jobs.register_handler("preview.product", handle_product_preview)
jobs.register_handler("preview.on_body", handle_on_body_preview)
jobs.register_handler("preview.avatar_3d", handle_avatar_preview)
jobs.register_handler("story.generate", handle_story_generate)
