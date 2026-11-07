from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.core.errors import Unauthenticated
from app.core.responses import ok
from app.core.security import create_access_token
from app.db.base import get_session
from app.models import User
from app.schemas.auth import LoginIn, MeOut, RegisterIn
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _me(user: User) -> dict:
    return MeOut.model_validate(user).model_dump(mode="json")


@router.post("/register", status_code=201)
def register(body: RegisterIn, session: Session = Depends(get_session)):
    user = auth_service.register_user(session, body.email, body.password, body.display_name)
    session.commit()
    return ok(_me(user))


@router.post("/login")
def login(body: LoginIn, session: Session = Depends(get_session)):
    user = auth_service.authenticate(session, body.email, body.password)
    if user is None:
        raise Unauthenticated("Invalid email or password")
    return ok({"access_token": create_access_token(user.id), "token_type": "bearer"})


@router.get("/me")
def me(user: User = Depends(current_user)):
    return ok(_me(user))
