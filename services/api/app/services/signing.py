import hashlib
import hmac
import uuid
from datetime import UTC, datetime

from app.core.config import settings


def _sign(file_id: uuid.UUID, expires_at: int) -> str:
    msg = f"{file_id}:{expires_at}".encode()
    return hmac.new(settings.file_url_secret.encode(), msg, hashlib.sha256).hexdigest()


def make_token(file_id: uuid.UUID, now: datetime | None = None, ttl: int | None = None) -> str:
    now = now or datetime.now(UTC)
    expires_at = int(now.timestamp()) + (ttl if ttl is not None else settings.file_url_ttl_seconds)
    return f"{expires_at}.{_sign(file_id, expires_at)}"


def verify_token(file_id: uuid.UUID, token: str, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    try:
        raw_exp, signature = token.split(".", 1)
        expires_at = int(raw_exp)
    except ValueError:
        return False
    if not hmac.compare_digest(signature, _sign(file_id, expires_at)):
        return False
    return int(now.timestamp()) <= expires_at
