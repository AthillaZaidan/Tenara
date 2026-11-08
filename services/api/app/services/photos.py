import io
import uuid
from datetime import UTC, datetime, timedelta

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppValidationError, InvalidTransition, NotFound
from app.models import BodyPhoto, File, PhotoConsent, Preview, User
from app.services import audit
from app.services.files import create_file
from app.services.storage import Storage

NOTICE_VERSION = "2026-11-v1"
PURPOSE = "measurement_and_tryon"
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
CONSENT_TEXT = (
    "Foto Anda diproses untuk estimasi ukuran dan pratinjau try-on. Foto asli bersifat privat, "
    "tidak dibagikan ke merchant, dan dihapus otomatis setelah masa simpan yang Anda pilih. Tailor "
    "terpilih hanya menerima ukuran yang Anda konfirmasi, kecuali Anda mengizinkan foto asli. "
    "Foto tidak dipakai untuk pelatihan model kecuali Anda mengizinkan terpisah.")


def _now() -> datetime:
    return datetime.now(UTC)


def create_consent(session: Session, user: User, *, retention_minutes: int | None,
                   share_original: bool, allow_training: bool) -> PhotoConsent:
    minutes = retention_minutes or settings.photo_default_retention_minutes
    if not (1 <= minutes <= settings.photo_max_retention_days * 1440):
        raise AppValidationError(
            f"Masa simpan harus antara 1 menit dan {settings.photo_max_retention_days} hari",
            field="retention_minutes")
    consent = PhotoConsent(user_id=user.id, purpose=PURPOSE, retention_minutes=minutes,
                           share_original_with_tailor=share_original,
                           allow_training_use=allow_training, notice_version=NOTICE_VERSION)
    session.add(consent)
    session.flush()
    audit.record(session, actor=user, action="photo.consent_given", target_type="photo_consent",
                 target_id=consent.id, metadata={"retention_minutes": minutes})
    return consent


def owned_consent(session: Session, user: User, consent_id: uuid.UUID) -> PhotoConsent:
    consent = session.get(PhotoConsent, consent_id)
    if consent is None or consent.user_id != user.id:
        raise NotFound("Consent not found")
    return consent


def upload_photo(session: Session, storage: Storage, user: User, data: bytes, content_type: str,
                 consent_id: uuid.UUID) -> BodyPhoto:
    consent = owned_consent(session, user, consent_id)
    if consent.revoked_at is not None:
        raise InvalidTransition("Persetujuan ini sudah dicabut")
    if content_type not in ALLOWED_TYPES:
        raise AppValidationError("Format foto harus JPEG, PNG atau WebP", field="file")
    if len(data) > settings.photo_max_bytes:
        raise AppValidationError("Foto terlalu besar", field="file")
    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise AppValidationError("File bukan gambar yang valid", field="file") from None
    if min(image.size) < 300:
        raise AppValidationError("Resolusi foto terlalu kecil (minimal 300 px pada sisi pendek)",
                                 field="file")
    if image.height < image.width * 0.9:
        raise AppValidationError("Gunakan foto potret: berdiri, seluruh badan, menghadap depan",
                                 field="file")
    clean = io.BytesIO()  # re-encoding drops EXIF (including any GPS location)
    image.save(clean, format="JPEG", quality=90)
    file = create_file(session, storage, owner_id=user.id, kind="body_photo", data=clean.getvalue(),
                       content_type="image/jpeg")
    photo = BodyPhoto(owner_id=user.id, file_id=file.id, consent_id=consent.id, width=image.width,
                      height=image.height,
                      delete_after=_now() + timedelta(minutes=consent.retention_minutes))
    session.add(photo)
    session.flush()
    audit.record(session, actor=user, action="photo.uploaded", target_type="body_photo",
                 target_id=photo.id)
    return photo


def owned_photo(session: Session, user: User, photo_id: uuid.UUID, *, stored_only: bool = True) -> BodyPhoto:
    photo = session.get(BodyPhoto, photo_id)
    if photo is None or photo.owner_id != user.id or (stored_only and photo.status != "stored"):
        raise NotFound("Photo not found")
    return photo


def load_image(session: Session, storage: Storage, photo: BodyPhoto) -> Image.Image:
    file = session.get(File, photo.file_id) if photo.file_id else None
    if photo.status != "stored" or file is None or file.deleted_at is not None:
        raise NotFound("Photo not available")
    return Image.open(io.BytesIO(storage.open(file.storage_key))).convert("RGB")


def _drop_file(session: Session, storage: Storage, file_id: uuid.UUID | None) -> None:
    file = session.get(File, file_id) if file_id else None
    if file is not None and file.deleted_at is None:
        storage.delete(file.storage_key)
        file.deleted_at = _now()


def delete_photo(session: Session, storage: Storage, photo: BodyPhoto, actor: User | None,
                 *, reason: str = "user_request") -> None:
    """Remove the raw photo and the private on-body images derived from it.

    The approved written specification, measurement set and order history are NOT touched.
    """
    _drop_file(session, storage, photo.file_id)
    for preview in session.scalars(select(Preview).where(Preview.body_photo_id == photo.id)):
        _drop_file(session, storage, preview.file_id)
        preview.file_id, preview.status = None, "deleted_with_photo"
    photo.status, photo.deleted_at, photo.file_id = "deleted", _now(), None
    session.flush()
    audit.record(session, actor=actor, action="photo.deleted", target_type="body_photo",
                 target_id=photo.id, metadata={"reason": reason})


def revoke_consent(session: Session, storage: Storage, user: User, consent: PhotoConsent) -> int:
    consent.revoked_at = _now()
    photos = list(session.scalars(select(BodyPhoto).where(
        BodyPhoto.consent_id == consent.id, BodyPhoto.status == "stored")))
    for photo in photos:
        delete_photo(session, storage, photo, user, reason="consent_revoked")
    audit.record(session, actor=user, action="photo.consent_revoked", target_type="photo_consent",
                 target_id=consent.id)
    return len(photos)


def purge_expired(session: Session, storage: Storage, now: datetime | None = None) -> int:
    expired = list(session.scalars(select(BodyPhoto).where(
        BodyPhoto.status == "stored", BodyPhoto.delete_after <= (now or _now()))))
    for photo in expired:
        delete_photo(session, storage, photo, None, reason="retention_expired")
    return len(expired)


def photo_out(photo: BodyPhoto) -> dict:
    return {"id": photo.id, "status": photo.status, "width": photo.width, "height": photo.height,
            "delete_after": photo.delete_after, "consent_id": photo.consent_id,
            "created_at": photo.created_at}


def sanitize_image(data: bytes) -> tuple[bytes, str]:
    """Decode, drop EXIF/metadata and re-encode. Raises AppValidationError for non-images."""
    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    except (UnidentifiedImageError, OSError):
        raise AppValidationError("File bukan gambar yang valid", field="file") from None
    out = io.BytesIO()
    if image.mode in ("RGBA", "LA", "P"):
        image.convert("RGBA").save(out, format="PNG")
        return out.getvalue(), "image/png"
    image.convert("RGB").save(out, format="JPEG", quality=90)
    return out.getvalue(), "image/jpeg"
