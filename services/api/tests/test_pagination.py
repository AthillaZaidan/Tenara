import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.errors import AppValidationError
from app.core.pagination import decode_cursor, encode_cursor, paginate
from app.models import File


@pytest.fixture
def files(session, make_user):
    owner = make_user()
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        File(owner_id=owner.id, kind="t", storage_key=f"k{i}", content_type="text/plain",
             size_bytes=1, created_at=base + timedelta(minutes=i))
        for i in range(5)
    ]
    session.add_all(rows)
    session.flush()
    return owner, rows


def test_cursor_roundtrip():
    ts, oid = datetime(2026, 1, 1, tzinfo=UTC), uuid.uuid4()
    assert decode_cursor(encode_cursor(ts, oid)) == (ts, oid)


@pytest.mark.parametrize("bad", ["!!!", "e30=", ""])
def test_bad_cursor_is_validation_error(bad):
    with pytest.raises(AppValidationError) as exc:
        decode_cursor(bad)
    assert exc.value.field == "cursor"


def test_pages_walk_newest_first(session, files):
    owner, _ = files
    stmt = select(File).where(File.owner_id == owner.id)
    seen, cursor = [], None
    while True:
        page = paginate(session, File, stmt, limit=2, cursor=cursor)
        seen += [f.storage_key for f in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == ["k4", "k3", "k2", "k1", "k0"]


def test_last_page_has_no_cursor(session, files):
    owner, _ = files
    page = paginate(session, File, select(File).where(File.owner_id == owner.id), limit=10)
    assert len(page["items"]) == 5
    assert page["next_cursor"] is None


def test_limit_is_clamped(session, files):
    owner, _ = files
    stmt = select(File).where(File.owner_id == owner.id)
    assert len(paginate(session, File, stmt, limit=0)["items"]) == 1
    assert len(paginate(session, File, stmt, limit=10_000)["items"]) == 5
