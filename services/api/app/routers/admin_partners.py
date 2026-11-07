import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.core.errors import NotFound
from app.core.pagination import paginate
from app.core.responses import ok
from app.db.base import get_session
from app.models import PartnerApplication, PartnerReview, User
from app.schemas.partner import ApplicationDecision, PartnerStatusChange
from app.services import partners as svc

router = APIRouter(prefix="/admin", tags=["admin-partners"])
Admin = Depends(require_role("admin"))


def _get(session: Session, app_id: uuid.UUID) -> PartnerApplication:
    app = session.get(PartnerApplication, app_id)
    if app is None:
        raise NotFound("Application not found")
    return app


@router.get("/partner-applications")
def list_applications(status: str | None = Query(default=None), type: str | None = Query(default=None),
                      limit: int = Query(default=20, ge=1, le=100),
                      cursor: str | None = Query(default=None), user: User = Admin,
                      session: Session = Depends(get_session)):
    stmt = select(PartnerApplication)
    if status:
        stmt = stmt.where(PartnerApplication.status == status)
    if type:
        stmt = stmt.where(PartnerApplication.type == type)
    page = paginate(session, PartnerApplication, stmt, limit=limit, cursor=cursor)
    return ok({"items": [svc.application_out(a) for a in page["items"]],
               "next_cursor": page["next_cursor"]})


@router.get("/partner-applications/{app_id}")
def get_application(app_id: uuid.UUID, user: User = Admin, session: Session = Depends(get_session)):
    app = _get(session, app_id)
    reviews = session.scalars(select(PartnerReview).where(PartnerReview.application_id == app.id)
                              .order_by(PartnerReview.created_at))
    out = svc.application_out(app)
    out["evidence"] = svc.evidence_links(session, user, app)
    out["reviews"] = [{"action": r.action, "reason": r.reason, "reviewer_id": r.reviewer_id,
                       "created_at": r.created_at} for r in reviews]
    session.commit()  # persists the evidence-access audit event
    return ok(out)


@router.post("/partner-applications/{app_id}/decision")
def decide(app_id: uuid.UUID, body: ApplicationDecision, user: User = Admin,
           session: Session = Depends(get_session)):
    app = svc.review_application(session, user, _get(session, app_id), body.action, body.reason)
    session.commit()
    return ok(svc.application_out(app))


@router.post("/partners/suspend")
def suspend(body: PartnerStatusChange, user: User = Admin, session: Session = Depends(get_session)):
    svc.set_partner_status(session, user, body.user_id, body.role, True, body.reason)
    session.commit()
    return ok({"status": "suspended"})


@router.post("/partners/reinstate")
def reinstate(body: PartnerStatusChange, user: User = Admin,
              session: Session = Depends(get_session)):
    svc.set_partner_status(session, user, body.user_id, body.role, False, body.reason)
    session.commit()
    return ok({"status": "active"})
