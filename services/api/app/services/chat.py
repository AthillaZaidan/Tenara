import base64
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppValidationError, Forbidden, NotFound
from app.models import (
    Conversation,
    ConversationMember,
    MerchantProfile,
    Message,
    TailorProfile,
    User,
)
from app.services import commerce as commerce_svc
from app.services import custom_requests as req_svc

MAX_BODY = 2000


def _now() -> datetime:
    return datetime.now(UTC)


def _partner_user(session: Session, merchant_id, tailor_id, with_role: str) -> uuid.UUID:
    if with_role == "merchant" and merchant_id:
        return session.get(MerchantProfile, merchant_id).user_id
    if with_role == "tailor" and tailor_id:
        return session.get(TailorProfile, tailor_id).user_id
    raise AppValidationError(f"Konteks ini tidak memiliki {with_role}", field="with")


def open_conversation(session: Session, user: User, *, order_id: uuid.UUID | None,
                      request_id: uuid.UUID | None, with_role: str) -> Conversation:
    if (order_id is None) == (request_id is None):
        raise AppValidationError("Provide exactly one of order_id or request_id", field="order_id")
    if order_id is not None:
        order, _roles = commerce_svc.get_order_for(session, user, order_id)
        kind, buyer_id = "order", order.buyer_id
        partner_id = _partner_user(session, order.merchant_id, order.tailor_id, with_role)
        subject = f"Pesanan {str(order.id)[:8]}"
    else:
        req, _roles = req_svc.get_for(session, user, request_id)
        kind, buyer_id = "request", req.buyer_id
        partner_id = _partner_user(session, req.merchant_id, req.tailor_id, with_role)
        subject = f"Permintaan kustom {str(req.id)[:8]}"
    # only the buyer or that specific partner may start the thread; other parties stay out
    if not (user.id == buyer_id or user.id == partner_id):
        raise Forbidden("Hanya pembeli atau mitra terkait yang dapat memulai percakapan ini")
    existing = session.scalar(select(Conversation).where(
        Conversation.kind == kind, Conversation.order_id == order_id,
        Conversation.request_id == request_id, Conversation.partner_user_id == partner_id,
        Conversation.claim_id.is_(None)))
    if existing is not None:
        return existing
    conv = Conversation(kind=kind, order_id=order_id, request_id=request_id,
                        partner_user_id=partner_id, subject=subject, created_by=user.id)
    session.add(conv)
    session.flush()
    session.add(ConversationMember(conversation_id=conv.id, user_id=buyer_id, role_label="buyer"))
    session.add(ConversationMember(conversation_id=conv.id, user_id=partner_id, role_label=with_role))
    session.flush()
    return conv


def create_claim_conversation(session: Session, claim_id: uuid.UUID, order_id: uuid.UUID,
                              buyer_id: uuid.UUID, target_user_id: uuid.UUID, target_role: str,
                              created_by: uuid.UUID) -> Conversation:
    conv = Conversation(kind="claim", order_id=order_id, claim_id=claim_id,
                        partner_user_id=target_user_id, subject=f"Klaim {str(claim_id)[:8]}",
                        created_by=created_by)
    session.add(conv)
    session.flush()
    session.add(ConversationMember(conversation_id=conv.id, user_id=buyer_id, role_label="buyer"))
    session.add(ConversationMember(conversation_id=conv.id, user_id=target_user_id,
                                   role_label=target_role))
    session.flush()
    return conv


def add_member(session: Session, conversation_id: uuid.UUID, user_id: uuid.UUID, label: str) -> None:
    if session.scalar(select(ConversationMember.id).where(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.user_id == user_id)) is None:
        session.add(ConversationMember(conversation_id=conversation_id, user_id=user_id,
                                       role_label=label))
        session.flush()


def member_conversation(session: Session, user: User, conv_id: uuid.UUID) -> Conversation:
    conv = session.get(Conversation, conv_id)
    member = conv and session.scalar(select(ConversationMember.id).where(
        ConversationMember.conversation_id == conv.id, ConversationMember.user_id == user.id))
    if conv is None or member is None:
        raise NotFound("Conversation not found")
    return conv


def send_message(session: Session, user: User, conv: Conversation, body: str) -> Message:
    text = body.strip()
    if not text or len(text) > MAX_BODY:
        raise AppValidationError(f"Pesan harus 1-{MAX_BODY} karakter", field="body")
    message = Message(conversation_id=conv.id, sender_id=user.id, body=text, created_at=_now())
    session.add(message)
    session.flush()
    return message


def _encode(created_at: datetime, message_id: uuid.UUID) -> str:
    raw = json.dumps({"c": created_at.isoformat(), "i": str(message_id)}).encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(data["c"]), uuid.UUID(data["i"])
    except (ValueError, KeyError, TypeError):
        raise AppValidationError("Invalid cursor", field="after") from None


def list_messages(session: Session, conv: Conversation, *, after: str | None, limit: int) -> dict:
    """Oldest first; `next_cursor` can be passed back as `after` to poll for new messages."""
    stmt = select(Message).where(Message.conversation_id == conv.id)
    if after:
        created_at, mid = _decode(after)
        stmt = stmt.where((Message.created_at > created_at)
                          | ((Message.created_at == created_at) & (Message.id > mid)))
    rows = list(session.scalars(stmt.order_by(Message.created_at, Message.id)
                                .limit(max(1, min(limit, 200)))))
    return {"items": [message_out(m) for m in rows],
            "next_cursor": _encode(rows[-1].created_at, rows[-1].id) if rows else after}


def message_out(m: Message) -> dict:
    return {"id": m.id, "sender_id": m.sender_id, "body": m.body, "created_at": m.created_at}


def conversation_out(session: Session, conv: Conversation, viewer: User) -> dict:
    members = session.execute(
        select(ConversationMember.user_id, ConversationMember.role_label)
        .where(ConversationMember.conversation_id == conv.id)).all()
    last = session.scalar(select(Message).where(Message.conversation_id == conv.id)
                          .order_by(Message.created_at.desc(), Message.id.desc()).limit(1))
    return {"id": conv.id, "kind": conv.kind, "subject": conv.subject, "order_id": conv.order_id,
            "request_id": conv.request_id, "claim_id": conv.claim_id,
            "members": [{"user_id": u, "role": r} for u, r in members],
            "last_message": message_out(last) if last else None,
            "viewer_id": viewer.id}


def my_conversations(session: Session, user: User) -> list[dict]:
    rows = session.scalars(
        select(Conversation).join(ConversationMember,
                                  ConversationMember.conversation_id == Conversation.id)
        .where(ConversationMember.user_id == user.id).order_by(Conversation.created_at.desc()))
    return [conversation_out(session, c, user) for c in rows]


def count_messages(session: Session, conv: Conversation) -> int:
    return session.scalar(select(func.count()).select_from(Message)
                          .where(Message.conversation_id == conv.id))

