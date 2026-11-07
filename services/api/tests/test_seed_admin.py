from sqlalchemy import select

from app.models import AuditEvent
from scripts.seed_admin import seed_admin


def _admin_roles(user):
    return [(r.role, r.status) for r in user.roles if r.role == "admin"]


def test_creates_admin(session):
    user = seed_admin(session, "Boss@Example.com", "password123")
    assert user.email == "boss@example.com"
    assert _admin_roles(user) == [("admin", "active")]


def test_is_idempotent(session):
    first = seed_admin(session, "boss@example.com", "password123")
    second = seed_admin(session, "boss@example.com", "other-password-1")
    assert first.id == second.id
    assert _admin_roles(second) == [("admin", "active")]


def test_promotes_existing_user_and_keeps_password(session, make_user):
    existing = make_user("boss@example.com")
    old_hash = existing.password_hash
    user = seed_admin(session, "boss@example.com", "different-pass-1")
    assert user.id == existing.id
    assert user.password_hash == old_hash
    assert _admin_roles(user) == [("admin", "active")]


def test_reactivates_suspended_admin(session, make_user):
    make_user("boss@example.com", roles=(("admin", "suspended"),))
    user = seed_admin(session, "boss@example.com", "password123")
    assert _admin_roles(user) == [("admin", "active")]


def test_writes_audit_event(session):
    user = seed_admin(session, "boss@example.com", "password123")
    ev = session.scalar(select(AuditEvent).where(AuditEvent.action == "admin.seeded"))
    assert ev is not None
    assert ev.target_id == str(user.id)
