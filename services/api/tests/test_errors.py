import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import (
    AppValidationError,
    Forbidden,
    IdempotencyConflict,
    NotFound,
    StaleRevision,
    Unauthenticated,
    register_error_handlers,
)
from app.core.responses import ok


class Body(BaseModel):
    n: int


def build() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/ok")
    def _ok():
        return ok({"x": 1})

    @app.get("/e/{name}")
    def _raise(name: str):
        raise {
            "unauth": Unauthenticated(),
            "forbidden": Forbidden(),
            "notfound": NotFound(),
            "stale": StaleRevision("old"),
            "idem": IdempotencyConflict(),
            "val": AppValidationError("bad", field="email"),
        }[name]

    @app.post("/body")
    def _body(b: Body):
        return ok({"n": b.n})

    return TestClient(app)


def test_ok_envelope():
    r = build().get("/ok")
    assert r.json() == {"data": {"x": 1}, "error": None}


@pytest.mark.parametrize(
    "name,status,code",
    [
        ("unauth", 401, "unauthenticated"),
        ("forbidden", 403, "forbidden"),
        ("notfound", 404, "not_found"),
        ("stale", 409, "stale_revision"),
        ("idem", 409, "idempotency_conflict"),
        ("val", 422, "validation_error"),
    ],
)
def test_app_errors(name, status, code):
    r = build().get(f"/e/{name}")
    assert r.status_code == status
    body = r.json()
    assert body["data"] is None
    assert body["error"]["code"] == code
    assert body["error"]["message"]


def test_field_included_when_given():
    assert build().get("/e/val").json()["error"]["field"] == "email"


def test_request_validation_error_uses_envelope():
    r = build().post("/body", json={"n": "abc"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error"
    assert err["field"] == "n"


def test_unknown_route_uses_envelope():
    r = build().get("/nope")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
