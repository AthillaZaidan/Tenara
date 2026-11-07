import uuid

from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.models import User


def get_owned_or_404[T](
    session: Session, model: type[T], obj_id: uuid.UUID, user: User, owner_attr: str = "owner_id"
) -> T:
    obj = session.get(model, obj_id)
    if obj is None or getattr(obj, owner_attr) != user.id:
        raise NotFound()
    return obj
