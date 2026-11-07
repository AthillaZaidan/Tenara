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

API_DIR = Path(__file__).resolve().parent.parent


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
def client(session):
    app.dependency_overrides[get_session] = lambda: session
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
