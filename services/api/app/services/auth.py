from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppValidationError
from app.core.security import hash_password, verify_password
from app.models import Role, RoleAssignment, RoleStatus, User, UserStatus

_DUMMY_HASH = hash_password("timing-equalizer")


def _normalize(email: str) -> str:
    return email.strip().lower()


def register_user(session: Session, email: str, password: str, display_name: str) -> User:
    email = _normalize(email)
    if session.scalar(select(User).where(User.email == email)):
        raise AppValidationError("Email is already registered", field="email")
    user = User(email=email, password_hash=hash_password(password),
                display_name=display_name.strip())
    try:
        with session.begin_nested():
            session.add(user)
            session.flush()
    except IntegrityError:
        raise AppValidationError("Email is already registered", field="email") from None
    session.add(RoleAssignment(user_id=user.id, role=Role.BUYER.value,
                               status=RoleStatus.ACTIVE.value))
    session.flush()
    session.refresh(user)
    return user


def authenticate(session: Session, email: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.email == _normalize(email)))
    if user is None:
        verify_password(_DUMMY_HASH, password)  # equalize timing
        return None
    if not verify_password(user.password_hash, password):
        return None
    if user.status != UserStatus.ACTIVE.value:
        return None
    return user
