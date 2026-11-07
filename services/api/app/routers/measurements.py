import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.core.responses import ok
from app.db.base import get_session
from app.models import User
from app.schemas.customization import ConfirmMeasurements, MeasurementCreate, MeasurementPatch
from app.services import customization as cust_svc
from app.services import measurements as svc

router = APIRouter(tags=["measurements"])


@router.post("/measurement-sets", status_code=201)
def create_set(body: MeasurementCreate, user: User = Depends(current_user),
               session: Session = Depends(get_session)):
    mset = svc.create_set(session, user, body.height_cm, body.values)
    session.commit()
    return ok(svc.set_out(session, mset))


@router.get("/measurement-sets/{set_id}")
def get_set(set_id: uuid.UUID, user: User = Depends(current_user),
            session: Session = Depends(get_session)):
    return ok(svc.set_out(session, svc.owned_set(session, user, set_id)))


@router.patch("/measurement-sets/{set_id}")
def patch_set(set_id: uuid.UUID, body: MeasurementPatch, user: User = Depends(current_user),
              session: Session = Depends(get_session)):
    mset = svc.patch_set(session, user, svc.owned_set(session, user, set_id),
                         body.expected_revision, body.values, body.height_cm)
    session.commit()
    return ok(svc.set_out(session, mset))


@router.post("/measurement-sets/{set_id}/confirm")
def confirm_set(set_id: uuid.UUID, body: ConfirmMeasurements, user: User = Depends(current_user),
                session: Session = Depends(get_session)):
    mset = svc.owned_set(session, user, set_id)
    cust = cust_svc.owned_customization(session, user, body.customization_id)
    svc.confirm_set(session, user, mset, cust_svc.definition_of(session, cust))
    session.commit()
    return ok(svc.set_out(session, mset))
