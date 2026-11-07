import uuid
from datetime import UTC, datetime, timedelta

from app.services.signing import make_token, verify_token

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_valid_token():
    fid = uuid.uuid4()
    assert verify_token(fid, make_token(fid, now=NOW), now=NOW + timedelta(seconds=10))


def test_expired_token():
    fid = uuid.uuid4()
    token = make_token(fid, now=NOW, ttl=60)
    assert not verify_token(fid, token, now=NOW + timedelta(seconds=61))


def test_token_bound_to_file():
    token = make_token(uuid.uuid4(), now=NOW)
    assert not verify_token(uuid.uuid4(), token, now=NOW)


def test_tampered_token():
    fid = uuid.uuid4()
    token = make_token(fid, now=NOW)
    assert not verify_token(fid, token[:-2] + "00", now=NOW)


def test_malformed_token():
    assert not verify_token(uuid.uuid4(), "garbage", now=NOW)
    assert not verify_token(uuid.uuid4(), "", now=NOW)
