import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, NotFound
from app.db.base import get_session
from app.models import File, FileVisibility
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
