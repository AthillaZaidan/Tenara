import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.models import File, Job, RoleAssignment, User


def _user(email="a@example.com"):
    return User(email=email, password_hash="x", display_name="A")


def test_user_defaults(session):
    u = _user()
    session.add(u)
    session.flush()
    session.refresh(u)
    assert u.id is not None
    assert u.status == "active"
    assert u.created_at is not None


def test_email_unique(session):
    session.add(_user())
    session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(_user())
        session.flush()


def test_role_must_be_valid(session):
    u = _user()
    session.add(u)
    session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(RoleAssignment(user_id=u.id, role="owner", status="active"))
        session.flush()


def test_role_unique_per_user(session):
    u = _user()
    session.add(u)
    session.flush()
    session.add(RoleAssignment(user_id=u.id, role="buyer", status="active"))
    session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(RoleAssignment(user_id=u.id, role="buyer", status="pending"))
        session.flush()


def test_job_defaults(session):
    u = _user()
    session.add(u)
    session.flush()
    j = Job(owner_id=u.id, kind="demo")
    session.add(j)
    session.flush()
    session.refresh(j)
    assert j.status == "queued"
    assert j.attempts == 0
    assert j.input == {}
    assert j.available_at is not None


def test_file_defaults(session):
    u = _user()
    session.add(u)
    session.flush()
    f = File(owner_id=u.id, kind="t", storage_key="k", content_type="text/plain", size_bytes=1)
    session.add(f)
    session.flush()
    session.refresh(f)
    assert f.visibility == "private"
    assert f.deleted_at is None


def test_vector_extension_enabled(session):
    row = session.execute(text("select 1 from pg_extension where extname = 'vector'")).first()
    assert row is not None


def test_models_match_migration(engine):
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
