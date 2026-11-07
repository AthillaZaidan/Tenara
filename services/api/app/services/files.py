import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import File, FileVisibility
from app.services.signing import make_token
from app.services.storage import Storage


def create_file(
    session: Session,
    storage: Storage,
    *,
    owner_id: uuid.UUID,
    kind: str,
    data: bytes,
    content_type: str,
    visibility: str = FileVisibility.PRIVATE.value,
) -> File:
    file_id = uuid.uuid4()
    key = f"{owner_id}/{file_id}"
    storage.put(key, data, content_type)
    file = File(id=file_id, owner_id=owner_id, kind=kind, storage_key=key,
                content_type=content_type, size_bytes=len(data), visibility=visibility)
    session.add(file)
    session.flush()
    return file


def signed_url(file: File, now: datetime | None = None) -> str:
    return f"/api/v1/files/{file.id}?token={make_token(file.id, now)}"


def delete_file(session: Session, storage: Storage, file: File) -> None:
    storage.delete(file.storage_key)
    file.deleted_at = datetime.now(UTC)
    session.flush()
