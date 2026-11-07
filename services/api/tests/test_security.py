import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_roundtrip():
    h = hash_password("password123")
    assert h != "password123"
    assert verify_password(h, "password123") is True
    assert verify_password(h, "wrong-password") is False


def test_verify_handles_garbage_hash():
    assert verify_password("not-a-hash", "whatever") is False


def test_token_roundtrip():
    uid = uuid.uuid4()
    assert decode_access_token(create_access_token(uid)) == uid


def test_token_lifetime_is_12_hours():
    uid = uuid.uuid4()
    now = datetime.now(UTC)
    payload = jwt.decode(
        create_access_token(uid, now=now), settings.jwt_secret, algorithms=["HS256"]
    )
    assert payload["exp"] - payload["iat"] == 12 * 3600


def test_expired_token_rejected():
    old = datetime.now(UTC) - timedelta(hours=13)
    assert decode_access_token(create_access_token(uuid.uuid4(), now=old)) is None


def test_tampered_token_rejected():
    token = create_access_token(uuid.uuid4())
    assert decode_access_token(token[:-2] + "xx") is None


def test_token_signed_with_other_secret_rejected():
    forged = jwt.encode({"sub": str(uuid.uuid4())}, "other-secret-of-sufficient-length-xx",
                        algorithm="HS256")
    assert decode_access_token(forged) is None
