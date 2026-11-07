import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.deps import require_role
from app.core.errors import register_error_handlers
from app.core.responses import ok
from app.db.base import get_session


@pytest.fixture
def role_client(session):
    app = FastAPI()
    register_error_handlers(app)
    app.dependency_overrides[get_session] = lambda: session

    @app.get("/merchant")
    def _merchant(user=Depends(require_role("merchant"))):
        return ok({"id": str(user.id)})

    @app.get("/merchant-or-admin")
    def _either(user=Depends(require_role("merchant", "admin"))):
        return ok({"id": str(user.id)})

    return TestClient(app)


def test_no_token_is_401(role_client):
    assert role_client.get("/merchant").status_code == 401


def test_buyer_only_is_403(role_client, make_user, auth_header):
    u = make_user()
    assert role_client.get("/merchant", headers=auth_header(u)).status_code == 403


@pytest.mark.parametrize("status,expected", [("pending", 403), ("suspended", 403), ("active", 200)])
def test_merchant_status_gates_access(role_client, make_user, auth_header, status, expected):
    u = make_user(roles=(("buyer", "active"), ("merchant", status)))
    assert role_client.get("/merchant", headers=auth_header(u)).status_code == expected


def test_any_listed_role_is_enough(role_client, make_user, auth_header):
    u = make_user(roles=(("admin", "active"),))
    assert role_client.get("/merchant-or-admin", headers=auth_header(u)).status_code == 200
