import uuid

import pytest
from sqlalchemy import func, select

from app.models import AuditEvent
from app.services import audit


def _count(session):
    return session.scalar(select(func.count()).select_from(AuditEvent))


def test_record_writes_row(session):
    target = uuid.uuid4()
    ev = audit.record(
        session, actor=None, action="thing.created", target_type="thing", target_id=target,
        metadata={"k": "v"},
    )
    assert ev.id is not None
    assert ev.target_id == str(target)
    assert ev.meta == {"k": "v"}
    assert ev.actor_user_id is None
    assert _count(session) == 1


def test_record_defaults_metadata_to_empty(session):
    ev = audit.record(session, actor=None, action="a", target_type="t", target_id="1")
    assert ev.meta == {}


def test_audit_rolls_back_with_caller(session):
    with pytest.raises(RuntimeError), session.begin_nested():
        audit.record(session, actor=None, action="a", target_type="t", target_id="1")
        raise RuntimeError("business step failed")
    assert _count(session) == 0
