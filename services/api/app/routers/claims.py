import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import current_user, require_role
from app.core.errors import Forbidden
from app.core.pagination import paginate
from app.core.responses import ok
from app.db.base import get_session
from app.models import Appeal, AuditEvent, Claim, User
from app.schemas.support import (
    AppealDecisionIn,
    AppealIn,
    ClaimCreate,
    EvidenceIn,
    EvidenceRequestIn,
    ProposalDecision,
    RemedyEventIn,
    ResponseIn,
)
from app.services import chat as chat_svc
from app.services import claims as svc
from app.services import commerce as commerce_svc

router = APIRouter(tags=["claims"])
Admin = Depends(require_role("admin"))


@router.post("/orders/{order_id}/claims", status_code=201)
def open_claim(order_id: uuid.UUID, body: ClaimCreate, user: User = Depends(current_user),
               session: Session = Depends(get_session)):
    claim = svc.open_claim(session, user, order_id, body.target, body.component, body.description,
                           body.evidence_file_ids)
    session.commit()
    return ok(svc.claim_out(session, claim, {"buyer"}))


@router.get("/claims")
def my_claims(limit: int = Query(default=20, ge=1, le=100), cursor: str | None = Query(default=None),
              user: User = Depends(current_user), session: Session = Depends(get_session)):
    stmt = select(Claim).where(or_(Claim.buyer_id == user.id, Claim.target_user_id == user.id))
    page = paginate(session, Claim, stmt, limit=limit, cursor=cursor)
    items = [{"id": c.id, "order_id": c.order_id, "status": c.status, "component": c.component,
              "target_role": c.target_role, "created_at": c.created_at} for c in page["items"]]
    return ok({"items": items, "next_cursor": page["next_cursor"]})


@router.get("/claims/{claim_id}")
def get_claim(claim_id: uuid.UUID, user: User = Depends(current_user),
              session: Session = Depends(get_session)):
    claim, roles = svc.claim_for(session, user, claim_id)
    return ok(svc.claim_out(session, claim, roles))


@router.post("/claims/{claim_id}/evidence", status_code=201)
def add_evidence(claim_id: uuid.UUID, body: EvidenceIn, user: User = Depends(current_user),
                 session: Session = Depends(get_session)):
    claim, _ = svc.claim_for(session, user, claim_id)
    row = svc.add_evidence(session, user, claim, body.file_id, body.note)
    session.commit()
    return ok({"id": row.id, "file_id": row.file_id})


@router.post("/claims/{claim_id}/responses", status_code=201)
def respond(claim_id: uuid.UUID, body: ResponseIn, user: User = Depends(current_user),
            session: Session = Depends(get_session)):
    claim, roles = svc.claim_for(session, user, claim_id)
    svc.partner_respond(session, user, claim, body.kind, body.reason,
                        body.proposal.model_dump() if body.proposal else None)
    session.commit()
    return ok(svc.claim_out(session, claim, roles))


@router.post("/claims/{claim_id}/proposals/{response_id}/decision")
def decide_proposal(claim_id: uuid.UUID, response_id: uuid.UUID, body: ProposalDecision,
                    user: User = Depends(current_user), session: Session = Depends(get_session)):
    claim, roles = svc.claim_for(session, user, claim_id)
    svc.buyer_decide(session, user, claim, response_id, body.decision)
    session.commit()
    return ok(svc.claim_out(session, claim, roles))


@router.post("/claims/{claim_id}/withdraw")
def withdraw_claim(claim_id: uuid.UUID, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    claim, roles = svc.claim_for(session, user, claim_id)
    svc.withdraw(session, user, claim)
    session.commit()
    return ok(svc.claim_out(session, claim, roles))


@router.post("/claims/{claim_id}/appeals", status_code=201)
def appeal_claim(claim_id: uuid.UUID, body: AppealIn, user: User = Depends(current_user),
                 session: Session = Depends(get_session)):
    claim, _ = svc.claim_for(session, user, claim_id)
    row = svc.appeal(session, user, claim, body.partner_rejection_id, body.reason, body.evidence_ids)
    session.commit()
    return ok(svc.appeal_summary(session, row))


@router.post("/claims/{claim_id}/remedy-events", status_code=201)
def remedy_event(claim_id: uuid.UUID, body: RemedyEventIn, user: User = Depends(current_user),
                 session: Session = Depends(get_session)):
    claim, roles = svc.claim_for(session, user, claim_id) if not commerce_svc.order_roles_admin(
        session, user) else (session.get(Claim, claim_id), {"admin"})
    if claim is None:
        raise Forbidden()
    event = svc.execute_remedy(session, user, claim, body.action, body.amount_idr, body.note,
                               is_admin="admin" in roles)
    session.commit()
    return ok({"id": event.id, "action": event.action, "amount_idr": event.amount_idr,
               "simulated": event.simulated, "claim_status": claim.status,
               "simulation_notice": commerce_svc.SIMULATION_NOTICE})


# ----- internal review (admin) -----

@router.get("/admin/appeals")
def appeal_queue(status: str | None = Query(default=None), limit: int = Query(default=20, ge=1, le=100),
                 cursor: str | None = Query(default=None), user: User = Admin,
                 session: Session = Depends(get_session)):
    stmt = select(Appeal)
    if status:
        stmt = stmt.where(Appeal.status == status)
    page = paginate(session, Appeal, stmt, limit=limit, cursor=cursor)
    return ok({"items": [svc.appeal_summary(session, a) for a in page["items"]],
               "next_cursor": page["next_cursor"]})


@router.post("/admin/appeals/{appeal_id}/start-review")
def start_review(appeal_id: uuid.UUID, user: User = Admin, session: Session = Depends(get_session)):
    row = svc.start_review(session, user, svc.get_appeal(session, appeal_id))
    session.commit()
    return ok(svc.appeal_summary(session, row))


@router.get("/admin/appeals/{appeal_id}")
def review_bundle(appeal_id: uuid.UUID, user: User = Admin, session: Session = Depends(get_session)):
    bundle = svc.review_bundle(session, user, svc.get_appeal(session, appeal_id))
    session.commit()  # persists the evidence-access audit event
    return ok(bundle)


@router.post("/admin/appeals/{appeal_id}/request-evidence", status_code=201)
def request_evidence(appeal_id: uuid.UUID, body: EvidenceRequestIn, user: User = Admin,
                     session: Session = Depends(get_session)):
    message = svc.request_evidence(session, user, svc.get_appeal(session, appeal_id), body.message)
    session.commit()
    return ok(chat_svc.message_out(message))


@router.post("/appeals/{appeal_id}/decision")
def decide_appeal(appeal_id: uuid.UUID, body: AppealDecisionIn, user: User = Admin,
                  session: Session = Depends(get_session)):
    decision = svc.decide(session, user, svc.get_appeal(session, appeal_id), outcome=body.outcome,
                          remedy_type=body.remedy_type, amount_idr=body.amount_idr,
                          reasoning=body.reasoning)
    session.commit()
    return ok({"id": decision.id, "outcome": decision.outcome, "remedy_type": decision.remedy_type,
               "amount_idr": decision.amount_idr, "requires_execution": decision.requires_execution})


# ----- admin audit trail -----

@router.get("/admin/audit-events")
def audit_events(action: str | None = Query(default=None), target_type: str | None = Query(default=None),
                 target_id: str | None = Query(default=None),
                 limit: int = Query(default=50, ge=1, le=200), cursor: str | None = Query(default=None),
                 user: User = Admin, session: Session = Depends(get_session)):
    stmt = select(AuditEvent)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    if target_type:
        stmt = stmt.where(AuditEvent.target_type == target_type)
    if target_id:
        stmt = stmt.where(AuditEvent.target_id == target_id)
    page = paginate(session, AuditEvent, stmt, limit=limit, cursor=cursor)
    items = [{"id": e.id, "actor_user_id": e.actor_user_id, "action": e.action,
              "target_type": e.target_type, "target_id": e.target_id, "metadata": e.meta,
              "created_at": e.created_at} for e in page["items"]]
    return ok({"items": items, "next_cursor": page["next_cursor"]})


