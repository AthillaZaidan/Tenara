import hashlib
import uuid
from collections.abc import Callable

from fastapi import Header
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppValidationError, IdempotencyConflict
from app.models import IdempotencyKey


def request_hash(method: str, path: str, body: bytes) -> str:
    return hashlib.sha256(f"{method}\n{path}\n".encode() + body).hexdigest()


def require_idempotency_key(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str:
    if not idempotency_key or len(idempotency_key) > 200:
        raise AppValidationError("Idempotency-Key header is required", field="Idempotency-Key")
    return idempotency_key


def _find(session: Session, user_id: uuid.UUID, key: str) -> IdempotencyKey | None:
    return session.scalar(
        select(IdempotencyKey).where(IdempotencyKey.user_id == user_id, IdempotencyKey.key == key)
    )


def _replay(row: IdempotencyKey, digest: str) -> tuple[int, dict]:
    if row.request_hash != digest:
        raise IdempotencyConflict("Idempotency-Key was already used for a different request")
    if row.response_status is None:
        raise IdempotencyConflict("A request with this Idempotency-Key is still in progress")
    return row.response_status, row.response_body or {}


def run_idempotent(
    session: Session,
    *,
    user_id: uuid.UUID,
    key: str,
    method: str,
    path: str,
    body: bytes,
    fn: Callable[[], tuple[int, dict]],
) -> tuple[int, dict]:
    """Run fn at most once per (user, key); replay the stored response afterwards.

    The key row is inserted first, so a concurrent duplicate blocks on the unique index
    and then sees the committed row (or fails with IntegrityError -> idempotency_conflict).
    """
    digest = request_hash(method, path, body)
    existing = _find(session, user_id, key)
    if existing is not None:
        return _replay(existing, digest)

    row = IdempotencyKey(user_id=user_id, key=key, method=method, path=path,
                         request_hash=digest)
    try:
        with session.begin_nested():
            session.add(row)
            session.flush()
    except IntegrityError:
        existing = _find(session, user_id, key)
        if existing is None:
            raise
        return _replay(existing, digest)

    status, payload = fn()
    row.response_status = status
    row.response_body = payload
    session.flush()
    return status, payload
