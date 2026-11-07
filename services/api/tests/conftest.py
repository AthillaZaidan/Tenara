from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.base import get_session
from app.main import app
from app.models import RoleAssignment, User
from app.services.embedding import FakeEmbedder, get_embedder

API_DIR = Path(__file__).resolve().parent.parent

# Tests create hundreds of users; cheap argon2 parameters keep the suite fast.
# Production keeps the library defaults (verification reads parameters from each hash).
from argon2 import PasswordHasher

import app.core.security as _security

_security._hasher = PasswordHasher(time_cost=1, memory_cost=512, parallelism=1)


def _ensure_test_db(url: str) -> None:
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("select 1 from pg_database where datname = :n"), {"n": target.database}
        ).scalar()
        if not exists:
            conn.execute(text(f'create database "{target.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def engine():
    _ensure_test_db(settings.test_database_url)
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.test_database_url)
    command.upgrade(cfg, "head")
    eng = create_engine(settings.test_database_url)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    conn = engine.connect()
    outer = conn.begin()
    s = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield s
    s.close()
    outer.rollback()
    conn.close()


@pytest.fixture
def embedder():
    return FakeEmbedder()


@pytest.fixture
def client(session, embedder):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_embedder] = lambda: embedder
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(session):
    def _make(email="user@example.com", roles=(("buyer", "active"),), password="password123"):
        user = User(email=email, password_hash=hash_password(password), display_name="Test User")
        session.add(user)
        session.flush()
        for role, status in roles:
            session.add(RoleAssignment(user_id=user.id, role=role, status=status))
        session.flush()
        session.refresh(user)
        return user

    return _make


@pytest.fixture
def auth_header():
    def _header(user):
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return _header


@pytest.fixture
def storage(tmp_path):
    from app.services.storage import LocalDiskStorage

    return LocalDiskStorage(tmp_path)


@pytest.fixture
def make_file(session, storage):
    def _make(owner, visibility="private", content_type="image/png"):
        from app.services.files import create_file

        return create_file(session, storage, owner_id=owner.id, kind="test", data=b"x",
                           content_type=content_type, visibility=visibility)

    return _make


@pytest.fixture
def make_partner(session, make_user):
    """An approved, active merchant or tailor with profile (bypasses the application flow)."""
    def _make(kind="merchant", email=None, shop="Toko Uji", city="Bandung", province="Jawa Barat"):
        from app.models import MerchantProfile, TailorProfile

        user = make_user(email or f"{kind}-{shop.lower().replace(' ', '')}@example.com",
                         roles=(("buyer", "active"), (kind, "active")))
        model = MerchantProfile if kind == "merchant" else TailorProfile
        profile = model(user_id=user.id, shop_name=shop, city=city, province=province)
        session.add(profile)
        session.flush()
        return user, profile

    return _make


@pytest.fixture
def published_entry(session, embedder, make_user):
    """A published Gallery entry, built through the service layer."""
    from app.services import gallery as g

    def _make(name="Tenun Ikat Sumba"):
        admin = make_user(f"curator-{name.replace(' ', '')}@example.com",
                          roles=(("admin", "active"),))
        source = g.create_source(session, admin, title="Dataset", license="CC BY 4.0")
        g.decide_source(session, admin, source, "approve", None)
        entry = g.create_entry(session, admin, name=name, region="NTT", summary="Ringkasan.")
        story = g.create_story(session, admin, entry, body="Cerita.",
                               citations=[{"source_id": source.id}])
        g.submit_story(session, admin, story)
        g.decide_story(session, admin, story, "approve", None, embedder)
        g.publish_entry(session, admin, entry, embedder)
        return entry

    return _make
