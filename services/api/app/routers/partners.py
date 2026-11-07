import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.core.errors import NotFound
from app.core.responses import ok
from app.db.base import get_session
from app.models import MerchantProfile, PartnerApplication, TailorCapability, TailorProfile, User
from app.schemas.partner import ApplicationCreate, ApplicationUpdate, CapabilityIn
from app.services import partners as svc

router = APIRouter(tags=["partners"])


@router.post("/partner-applications", status_code=201)
def create_application(body: ApplicationCreate, user: User = Depends(current_user),
                       session: Session = Depends(get_session)):
    app = svc.create_application(session, user, body.type, body.data)
    session.commit()
    return ok(svc.application_out(app))


@router.get("/partner-applications/mine")
def my_applications(user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = session.scalars(select(PartnerApplication)
                           .where(PartnerApplication.applicant_id == user.id)
                           .order_by(PartnerApplication.created_at.desc()))
    return ok([svc.application_out(a) for a in rows])


@router.patch("/partner-applications/{app_id}")
def update_application(app_id: uuid.UUID, body: ApplicationUpdate,
                       user: User = Depends(current_user), session: Session = Depends(get_session)):
    app = svc.update_application(session, user, svc.get_own_application(session, user, app_id),
                                 body.data)
    session.commit()
    return ok(svc.application_out(app))


@router.post("/partner-applications/{app_id}/submit")
def submit_application(app_id: uuid.UUID, user: User = Depends(current_user),
                       session: Session = Depends(get_session)):
    app = svc.submit_application(session, user, svc.get_own_application(session, user, app_id))
    session.commit()
    return ok(svc.application_out(app))


# ----- public partner profiles -----

@router.get("/merchants/{profile_id}")
def merchant_profile(profile_id: uuid.UUID, session: Session = Depends(get_session)):
    profile = session.get(MerchantProfile, profile_id)
    if profile is None or profile.status != "active":
        raise NotFound("Merchant not found")
    return ok(svc.merchant_public(profile))


@router.get("/tailors/{profile_id}")
def tailor_profile(profile_id: uuid.UUID, session: Session = Depends(get_session)):
    profile = session.get(TailorProfile, profile_id)
    if profile is None or profile.status != "active":
        raise NotFound("Tailor not found")
    return ok(svc.tailor_public(session, profile))


# ----- tailor capabilities (own) -----

@router.get("/tailor/capabilities")
def my_capabilities(user: User = Depends(current_user), session: Session = Depends(get_session)):
    tailor = svc.active_tailor(session, user)
    return ok([svc.capability_out(c) for c in svc.capabilities(session, tailor.id)])


@router.put("/tailor/capabilities/{template_code}")
def put_capability(template_code: str, body: CapabilityIn, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    from app.core.errors import AppValidationError
    from app.models.partner import TEMPLATE_CODES

    if template_code not in TEMPLATE_CODES:
        raise AppValidationError("Unknown template code", field="template_code")
    tailor = svc.active_tailor(session, user)
    cap = svc.upsert_capability(session, tailor, template_code, **body.model_dump())
    session.commit()
    return ok(svc.capability_out(cap))


@router.delete("/tailor/capabilities/{template_code}")
def delete_capability(template_code: str, user: User = Depends(current_user),
                      session: Session = Depends(get_session)):
    tailor = svc.active_tailor(session, user)
    cap = session.scalar(select(TailorCapability).where(
        TailorCapability.tailor_id == tailor.id, TailorCapability.template_code == template_code))
    if cap is None:
        raise NotFound("Capability not found")
    session.delete(cap)
    session.commit()
    return ok({"deleted": template_code})
