import uuid

from fastapi import APIRouter, Depends, Form, Query, UploadFile
from fastapi import File as FormFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import current_user
from app.core.errors import AppValidationError, Forbidden, InvalidTransition, NotFound
from app.core.ownership import get_owned_or_404
from app.core.responses import ok
from app.db.base import get_session
from app.models import Claim, ClaimEvidence, File, FileVisibility, User
from app.services import audit
from app.services import commerce as commerce_svc
from app.services import files as files_service
from app.services.claims import OPEN_STATUSES
from app.services.partners import active_merchant
from app.services.photos import sanitize_image
from app.services.signing import make_token, verify_token
from app.services.storage import Storage, get_storage

router = APIRouter(tags=["files"])


@router.get("/files/{file_id}")
def download(
    file_id: uuid.UUID,
    token: str | None = Query(default=None),
    session: Session = Depends(get_session),
    storage: Storage = Depends(get_storage),
):
    file = session.get(File, file_id)
    if file is None or file.deleted_at is not None:
        raise NotFound("File not found")
    if file.visibility != FileVisibility.PUBLIC.value and not (
        token and verify_token(file.id, token)
    ):
        raise Forbidden("Invalid or expired file token")
    try:
        data = storage.open(file.storage_key)
    except FileNotFoundError:
        raise NotFound("File not found") from None
    return Response(content=data, media_type=file.content_type)


@router.get("/me/files")
def my_files(kind: str | None = Query(default=None), user: User = Depends(current_user),
             session: Session = Depends(get_session)):
    stmt = select(File).where(File.owner_id == user.id, File.deleted_at.is_(None))
    if kind:
        stmt = stmt.where(File.kind == kind)
    rows = session.scalars(stmt.order_by(File.created_at.desc()))
    return ok([{"id": f.id, "kind": f.kind, "content_type": f.content_type,
                "size_bytes": f.size_bytes, "visibility": f.visibility,
                "created_at": f.created_at} for f in rows])


@router.delete("/files/{file_id}")
def delete_my_file(file_id: uuid.UUID, user: User = Depends(current_user),
                   session: Session = Depends(get_session),
                   storage: Storage = Depends(get_storage)):
    file = get_owned_or_404(session, File, file_id, user)
    if file.deleted_at is not None:
        raise NotFound("File not found")
    in_open_claim = session.scalar(
        select(ClaimEvidence.id).join(Claim, Claim.id == ClaimEvidence.claim_id)
        .where(ClaimEvidence.file_id == file.id, Claim.status.in_(OPEN_STATUSES)).limit(1))
    if in_open_claim:
        raise InvalidTransition("File ini menjadi bukti klaim yang masih berjalan")
    files_service.delete_file(session, storage, file)
    audit.record(session, actor=user, action="file.deleted", target_type="file", target_id=file.id)
    session.commit()
    return ok({"deleted": str(file.id)})


# kind -> (visibility, accepts PDF, who may upload)
UPLOAD_KINDS = {
    "verification_doc": ("private", True, "any"),
    "claim_evidence": ("private", True, "any"),
    "listing_photo": ("public", False, "merchant"),
    "reference_image": ("public", False, "admin"),
}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/files", status_code=201)
async def upload_file(file: UploadFile = FormFile(...), kind: str = Form(...),
                      user: User = Depends(current_user), session: Session = Depends(get_session),
                      storage: Storage = Depends(get_storage)):
    """Generic upload. Evidence stays private (signed URLs); listing/reference photos are public."""
    if kind not in UPLOAD_KINDS:
        raise AppValidationError(f"kind harus salah satu dari {sorted(UPLOAD_KINDS)}", field="kind")
    visibility, allows_pdf, who = UPLOAD_KINDS[kind]
    if who == "merchant":
        active_merchant(session, user)
    elif who == "admin" and not commerce_svc.order_roles_admin(session, user):
        raise Forbidden()
    data = await file.read(settings.upload_max_bytes + 1)
    if len(data) > settings.upload_max_bytes:
        raise AppValidationError("File terlalu besar", field="file")
    ctype = file.content_type or ""
    if allows_pdf and ctype == "application/pdf":
        if not data.startswith(b"%PDF"):
            raise AppValidationError("File bukan PDF yang valid", field="file")
    elif ctype in IMAGE_TYPES:
        data, ctype = sanitize_image(data)  # strips EXIF/GPS
    else:
        allowed = "JPEG/PNG/WebP" + (" atau PDF" if allows_pdf else "")
        raise AppValidationError(f"Format harus {allowed}", field="file")
    stored = files_service.create_file(session, storage, owner_id=user.id, kind=kind, data=data,
                                       content_type=ctype, visibility=visibility)
    audit.record(session, actor=user, action="file.uploaded", target_type="file",
                 target_id=stored.id, metadata={"kind": kind})
    session.commit()
    url = (f"/api/v1/files/{stored.id}" if visibility == "public"
           else f"/api/v1/files/{stored.id}?token={make_token(stored.id)}")
    return ok({"id": stored.id, "kind": kind, "visibility": visibility, "content_type": ctype,
               "size_bytes": stored.size_bytes, "url": url})
