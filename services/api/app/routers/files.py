import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.core.errors import Forbidden, InvalidTransition, NotFound
from app.core.ownership import get_owned_or_404
from app.core.responses import ok
from app.db.base import get_session
from app.models import Claim, ClaimEvidence, File, FileVisibility, User
from app.services import audit
from app.services import files as files_service
from app.services.claims import OPEN_STATUSES
from app.services.signing import verify_token
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
