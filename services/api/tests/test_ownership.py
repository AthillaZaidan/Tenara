import uuid

import pytest

from app.core.errors import NotFound
from app.core.ownership import get_owned_or_404
from app.models import File


def _file(owner_id):
    return File(owner_id=owner_id, kind="t", storage_key="k", content_type="text/plain",
                size_bytes=1)


def test_owner_gets_object(session, make_user):
    a = make_user("a@example.com")
    f = _file(a.id)
    session.add(f)
    session.flush()
    assert get_owned_or_404(session, File, f.id, a).id == f.id


def test_other_user_gets_404(session, make_user):
    a, b = make_user("a@example.com"), make_user("b@example.com")
    f = _file(a.id)
    session.add(f)
    session.flush()
    with pytest.raises(NotFound):
        get_owned_or_404(session, File, f.id, b)


def test_missing_object_gets_404(session, make_user):
    with pytest.raises(NotFound):
        get_owned_or_404(session, File, uuid.uuid4(), make_user())
