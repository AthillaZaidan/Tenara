import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.main import app
from app.services.files import create_file, delete_file, signed_url
from app.services.signing import make_token
from app.services.storage import LocalDiskStorage, get_storage


@pytest.fixture
def storage(tmp_path, client):
    s = LocalDiskStorage(tmp_path)
    app.dependency_overrides[get_storage] = lambda: s
    return s


def _make(session, storage, owner, visibility="private"):
    f = create_file(session, storage, owner_id=owner.id, kind="body_photo", data=b"PNGDATA",
                    content_type="image/png", visibility=visibility)
    session.flush()
    return f


def test_private_file_with_valid_token(client, session, storage, make_user):
    f = _make(session, storage, make_user())
    r = client.get(signed_url(f))
    assert r.status_code == 200
    assert r.content == b"PNGDATA"
    assert r.headers["content-type"] == "image/png"


def test_private_file_without_token_is_403(client, session, storage, make_user):
    f = _make(session, storage, make_user())
    r = client.get(f"/api/v1/files/{f.id}")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_expired_token_is_403(client, session, storage, make_user):
    f = _make(session, storage, make_user())
    old = datetime.now(UTC) - timedelta(hours=1)
    r = client.get(f"/api/v1/files/{f.id}?token={make_token(f.id, now=old)}")
    assert r.status_code == 403


def test_public_file_needs_no_token(client, session, storage, make_user):
    f = _make(session, storage, make_user(), visibility="public")
    assert client.get(f"/api/v1/files/{f.id}").status_code == 200


def test_unknown_file_is_404(client, storage):
    assert client.get(f"/api/v1/files/{uuid.uuid4()}").status_code == 404


def test_deleted_file_is_404(client, session, storage, make_user):
    f = _make(session, storage, make_user())
    url = signed_url(f)
    delete_file(session, storage, f)
    assert client.get(url).status_code == 404
