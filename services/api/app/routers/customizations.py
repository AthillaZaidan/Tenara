import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.core.errors import NotFound
from app.core.pagination import paginate
from app.core.responses import ok
from app.db.base import get_session
from app.models import Customization, DesignRevision, MeasurementSet, User
from app.schemas.customization import (
    AttachMeasurements,
    CustomizationCreate,
    PromptChangeIn,
    RevisionIn,
)
from app.services import customization as svc
from app.services import material as material_svc
from app.services import measurements as meas_svc

router = APIRouter(tags=["customizations"])


def _out(session: Session, cust: Customization) -> dict:
    defn = svc.definition_of(session, cust)
    rev = svc.get_revision(session, cust, cust.current_revision)
    mset = session.get(MeasurementSet, cust.measurement_set_id) if cust.measurement_set_id else None
    est = material_svc.current_estimate(session, cust)
    est_stale = bool(est and material_svc.stale_reasons(session, cust, est))
    ready = bool(not rev.open_clarifications and mset and mset.status == "confirmed"
                 and est and not est_stale)
    return {
        "id": cust.id, "listing_id": cust.listing_id, "entry_id": cust.entry_id,
        "template": {"code": cust.template_code, "name": defn["name"],
                     "required_dimensions": defn["required_dimensions"]},
        "current_revision": cust.current_revision, "state": rev.state,
        "open_clarifications": rev.open_clarifications,
        "measurement_set": ({"id": mset.id, "status": mset.status, "revision": mset.revision}
                            if mset else None),
        "material_estimate": ({"id": est.id, "stale": est_stale} if est else None),
        "ready_for_tailor_validation": ready,
        "created_at": cust.created_at,
    }


@router.post("/customizations", status_code=201)
def create(body: CustomizationCreate, user: User = Depends(current_user),
           session: Session = Depends(get_session)):
    cust = svc.create_customization(session, user, body.listing_id, body.template_code)
    session.commit()
    return ok(_out(session, cust))


@router.get("/customizations")
def mine(limit: int = Query(default=20, ge=1, le=100), cursor: str | None = Query(default=None),
         user: User = Depends(current_user), session: Session = Depends(get_session)):
    stmt = select(Customization).where(Customization.buyer_id == user.id)
    page = paginate(session, Customization, stmt, limit=limit, cursor=cursor)
    return ok({"items": [_out(session, c) for c in page["items"]], "next_cursor": page["next_cursor"]})


@router.get("/customizations/{cust_id}")
def get_one(cust_id: uuid.UUID, user: User = Depends(current_user),
            session: Session = Depends(get_session)):
    return ok(_out(session, svc.owned_customization(session, user, cust_id)))


@router.post("/customizations/{cust_id}/prompt-changes")
def prompt_changes(cust_id: uuid.UUID, body: PromptChangeIn, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    cust = svc.owned_customization(session, user, cust_id)
    request = svc.propose(session, user, cust, body.expected_design_revision, body.prompt)
    session.commit()
    return ok(svc.proposal_out(request))


@router.post("/customizations/{cust_id}/revisions", status_code=201)
def create_revision(cust_id: uuid.UUID, body: RevisionIn, user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
    cust = svc.owned_customization(session, user, cust_id)
    revision = svc.apply_revision(
        session, user, cust, body.expected_design_revision, proposal_id=body.proposal_id,
        resolutions=body.resolutions, changes=body.changes, revert_to=body.revert_to_revision)
    session.commit()
    return ok(svc.revision_out(revision))


@router.get("/customizations/{cust_id}/revisions")
def list_revisions(cust_id: uuid.UUID, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    cust = svc.owned_customization(session, user, cust_id)
    rows = session.scalars(select(DesignRevision).where(DesignRevision.customization_id == cust.id)
                           .order_by(DesignRevision.revision.desc()))
    return ok([svc.revision_out(r) for r in rows])


@router.get("/customizations/{cust_id}/revisions/{revision}")
def get_revision(cust_id: uuid.UUID, revision: int, user: User = Depends(current_user),
                 session: Session = Depends(get_session)):
    cust = svc.owned_customization(session, user, cust_id)
    return ok(svc.revision_out(svc.get_revision(session, cust, revision)))


@router.post("/customizations/{cust_id}/measurement-set")
def attach_measurements(cust_id: uuid.UUID, body: AttachMeasurements,
                        user: User = Depends(current_user), session: Session = Depends(get_session)):
    cust = svc.owned_customization(session, user, cust_id)
    meas_svc.attach(session, user, cust, body.measurement_set_id)
    session.commit()
    return ok(_out(session, cust))


@router.post("/customizations/{cust_id}/material-estimates", status_code=201)
def create_estimate(cust_id: uuid.UUID, user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
    cust = svc.owned_customization(session, user, cust_id)
    est = material_svc.estimate_for(session, user, cust)
    session.commit()
    return ok(material_svc.estimate_out(session, cust, est))


@router.get("/customizations/{cust_id}/material-estimates/current")
def current_estimate(cust_id: uuid.UUID, user: User = Depends(current_user),
                     session: Session = Depends(get_session)):
    cust = svc.owned_customization(session, user, cust_id)
    est = material_svc.current_estimate(session, cust)
    if est is None:
        raise NotFound("No material estimate yet")
    return ok(material_svc.estimate_out(session, cust, est))


@router.post("/customizations/{cust_id}/product-previews", status_code=202)
def product_preview(cust_id: uuid.UUID, user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
    cust = svc.owned_customization(session, user, cust_id)
    preview = svc.request_preview(session, user, cust)
    session.commit()
    return ok(svc.preview_out(session, preview))


@router.get("/previews/{preview_id}")
def get_preview(preview_id: uuid.UUID, user: User = Depends(current_user),
                session: Session = Depends(get_session)):
    return ok(svc.preview_out(session, svc.owned_preview(session, user, preview_id)))
