import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.core.errors import NotFound
from app.core.responses import ok
from app.db.base import get_session
from app.models import GarmentTemplate, User
from app.services import listings as listings_svc
from app.services import templates as svc

router = APIRouter(tags=["templates"])


@router.get("/garment-templates")
def list_templates(session: Session = Depends(get_session)):
    return ok(svc.list_templates(session))


@router.get("/garment-templates/{code}")
def get_template(code: str, session: Session = Depends(get_session)):
    template = session.get(GarmentTemplate, code.upper())
    version = svc.latest_version(session, code.upper()) if template else None
    if template is None or version is None:
        raise NotFound("Template not found")
    return ok(svc.template_out(template, version))


@router.get("/listings/{listing_id}/templates")
def listing_templates(listing_id: uuid.UUID, session: Session = Depends(get_session)):
    listing = listings_svc.public_listing(session, listing_id)
    return ok(svc.compatibility(session, listing))


@router.post("/admin/garment-templates/sync")
def sync_templates(user: User = Depends(require_role("admin")),
                   session: Session = Depends(get_session)):
    result = svc.sync_templates(session, user)
    session.commit()
    return ok(result)
