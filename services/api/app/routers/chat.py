import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.core.responses import ok
from app.db.base import get_session
from app.models import User
from app.schemas.support import ConversationCreate, MessageIn
from app.services import chat as svc

router = APIRouter(tags=["chat"])


@router.post("/conversations", status_code=201)
def open_conversation(body: ConversationCreate, user: User = Depends(current_user),
                      session: Session = Depends(get_session)):
    conv = svc.open_conversation(session, user, order_id=body.order_id,
                                 request_id=body.request_id, with_role=body.with_)
    session.commit()
    return ok(svc.conversation_out(session, conv, user))


@router.get("/conversations")
def list_conversations(user: User = Depends(current_user), session: Session = Depends(get_session)):
    return ok(svc.my_conversations(session, user))


@router.get("/conversations/{conv_id}/messages")
def list_messages(conv_id: uuid.UUID, after: str | None = Query(default=None),
                  limit: int = Query(default=50, ge=1, le=200), user: User = Depends(current_user),
                  session: Session = Depends(get_session)):
    conv = svc.member_conversation(session, user, conv_id)
    return ok(svc.list_messages(session, conv, after=after, limit=limit))


@router.post("/conversations/{conv_id}/messages", status_code=201)
def send_message(conv_id: uuid.UUID, body: MessageIn, user: User = Depends(current_user),
                 session: Session = Depends(get_session)):
    conv = svc.member_conversation(session, user, conv_id)
    message = svc.send_message(session, user, conv, body.body)
    session.commit()
    return ok(svc.message_out(message))
