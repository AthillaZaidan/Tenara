import uuid

from sqlalchemy.orm import Session

from app.models import AuditEvent, User


def record(
    session: Session,
    *,
    actor: User | uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: str | uuid.UUID,
    metadata: dict | None = None,
) -> AuditEvent:
    """Write an audit row in the caller's transaction (commits/rolls back with it)."""
    actor_id = actor.id if isinstance(actor, User) else actor
    event = AuditEvent(
        actor_user_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        meta=metadata or {},
    )
    session.add(event)
    session.flush()
    return event
