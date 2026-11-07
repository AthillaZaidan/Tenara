import base64
import json
import uuid
from datetime import datetime

from sqlalchemy import Select, tuple_
from sqlalchemy.orm import Session

from app.core.errors import AppValidationError

MAX_LIMIT = 100


def encode_cursor(created_at: datetime, obj_id: uuid.UUID) -> str:
    raw = json.dumps({"c": created_at.isoformat(), "i": str(obj_id)}).encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(data["c"]), uuid.UUID(data["i"])
    except (ValueError, KeyError, TypeError):
        raise AppValidationError("Invalid cursor", field="cursor") from None


def paginate(
    session: Session, model, stmt: Select, *, limit: int = 20, cursor: str | None = None
) -> dict:
    """Keyset pagination over (created_at, id), newest first."""
    limit = max(1, min(limit, MAX_LIMIT))
    if cursor:
        created_at, obj_id = decode_cursor(cursor)
        stmt = stmt.where(tuple_(model.created_at, model.id) < tuple_(created_at, obj_id))
    rows = list(
        session.scalars(
            stmt.order_by(model.created_at.desc(), model.id.desc()).limit(limit + 1)
        )
    )
    items = rows[:limit]
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if len(rows) > limit else None
    return {"items": items, "next_cursor": next_cursor}
