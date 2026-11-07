"""Create (or promote) an admin user.

Usage:  ADMIN_EMAIL=you@example.com ADMIN_PASSWORD=... uv run python -m scripts.seed_admin
"""
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import SessionLocal
from app.models import Role, RoleAssignment, RoleStatus, User
from app.services import audit


def seed_admin(session: Session, email: str, password: str, display_name: str = "Admin") -> User:
    email = email.strip().lower()
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, password_hash=hash_password(password),
                    display_name=display_name)
        session.add(user)
        session.flush()
    assignment = session.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user.id, RoleAssignment.role == Role.ADMIN.value
        )
    )
    now = datetime.now(UTC)
    if assignment is None:
        session.add(RoleAssignment(user_id=user.id, role=Role.ADMIN.value,
                                   status=RoleStatus.ACTIVE.value, decided_at=now))
    else:
        assignment.status = RoleStatus.ACTIVE.value
        assignment.decided_at = now
    audit.record(session, actor=None, action="admin.seeded", target_type="user",
                 target_id=user.id)
    session.flush()
    session.refresh(user)
    return user


def main() -> None:
    email, password = os.environ.get("ADMIN_EMAIL"), os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        sys.exit("Set ADMIN_EMAIL and ADMIN_PASSWORD")
    with SessionLocal() as session:
        user = seed_admin(session, email, password)
        session.commit()
    print(f"Admin ready: {user.email}")


if __name__ == "__main__":
    main()
