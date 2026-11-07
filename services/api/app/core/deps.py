from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, Unauthenticated
from app.core.security import decode_access_token
from app.db.base import get_session
from app.models import RoleStatus, User, UserStatus

_bearer = HTTPBearer(auto_error=False)


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> User:
    if creds is None:
        raise Unauthenticated()
    user_id = decode_access_token(creds.credentials)
    user = session.get(User, user_id) if user_id else None
    if user is None or user.status != UserStatus.ACTIVE.value:
        raise Unauthenticated()
    return user


def require_role(*roles: str):
    wanted = set(roles)

    def dependency(user: User = Depends(current_user)) -> User:
        active = {r.role for r in user.roles if r.status == RoleStatus.ACTIVE.value}
        if not active & wanted:
            raise Forbidden()
        return user

    return dependency
