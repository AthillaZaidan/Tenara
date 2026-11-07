import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.errors import IdempotencyConflict, register_error_handlers
from app.core.responses import ok
from app.models import IdempotencyKey
from app.services.idempotency import request_hash, require_idempotency_key, run_idempotent


def _call(session, user, fn, *, key="k1", body=b'{"a":1}', path="/orders"):
    return run_idempotent(
        session, user_id=user.id, key=key, method="POST", path=path, body=body, fn=fn
    )


def test_first_call_executes_and_stores(session, make_user):
    user, calls = make_user(), []

    def fn():
        calls.append(1)
        return 201, {"id": "o1"}

    assert _call(session, user, fn) == (201, {"id": "o1"})
    assert calls == [1]
    row = session.query(IdempotencyKey).one()
    assert row.response_status == 201
    assert row.response_body == {"id": "o1"}


def test_replay_returns_stored_response_without_running_fn(session, make_user):
    user, calls = make_user(), []

    def fn():
        calls.append(1)
        return 201, {"id": "o1"}

    first = _call(session, user, fn)
    second = _call(session, user, fn)
    assert first == second
    assert calls == [1]


def test_same_key_different_request_conflicts(session, make_user):
    user = make_user()
    _call(session, user, lambda: (201, {}))
    with pytest.raises(IdempotencyConflict):
        _call(session, user, lambda: (201, {}), body=b'{"a":2}')


def test_in_progress_key_conflicts(session, make_user):
    user = make_user()
    session.add(IdempotencyKey(
        user_id=user.id, key="k1", method="POST", path="/orders",
        request_hash=request_hash("POST", "/orders", b'{"a":1}'),
    ))
    session.flush()
    with pytest.raises(IdempotencyConflict):
        _call(session, user, lambda: (201, {}))


def test_keys_are_scoped_per_user(session, make_user):
    a, b = make_user("a@example.com"), make_user("b@example.com")
    calls = []

    def fn():
        calls.append(1)
        return 201, {}

    _call(session, a, fn)
    _call(session, b, fn)
    assert calls == [1, 1]


def test_missing_header_is_validation_error():
    app = FastAPI()
    register_error_handlers(app)

    @app.post("/x")
    def _x(key: str = Depends(require_idempotency_key)):
        return ok({"key": key})

    c = TestClient(app)
    assert c.post("/x").status_code == 422
    r = c.post("/x", headers={"Idempotency-Key": "abc"})
    assert r.json()["data"] == {"key": "abc"}
