import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import current_user
from app.core.errors import Forbidden, NotFound
from app.core.pagination import paginate
from app.core.responses import ok
from app.db.base import get_session
from app.models import MerchantProfile, OrderAmendment, Quote, TailorProfile, User
from app.models.custom import CustomRequest
from app.schemas.custom import (
    AmendmentDecision,
    AmendmentIn,
    CustomRequestCreate,
    CustomRequestUpdate,
    InspectionIn,
    MerchantDecisionIn,
    QuoteAcceptIn,
    QuoteIssueIn,
    SpecIn,
    TailorDecisionIn,
)
from app.services import commerce as commerce_svc
from app.services import custom_orders as orders_svc
from app.services import custom_requests as svc
from app.services import customization as cust_svc
from app.services import matching
from app.services.idempotency import require_idempotency_key, run_idempotent

router = APIRouter(tags=["custom-orders"])


def _req(session: Session, user: User, req_id: uuid.UUID, allowed: set[str]):
    req, roles = svc.get_for(session, user, req_id)
    svc.not_participant(roles, allowed)
    return req, roles


# ----- tailor recommendations -----

@router.get("/tailors/recommendations")
def tailor_recommendations(customization_id: uuid.UUID, delivery_address_id: uuid.UUID,
                           user: User = Depends(current_user),
                           session: Session = Depends(get_session)):
    cust = cust_svc.owned_customization(session, user, customization_id)
    address = commerce_svc.owned_address(session, user, delivery_address_id)
    items = matching.recommendations(session, cust, commerce_svc.address_out(address))
    return ok({"items": items,
               "notice": "Peringkat hanya saran berdasarkan data yang dideklarasikan tailor. "
                         "Anda yang memilih, dan tailor tetap harus memvalidasi."})


# ----- buyer -----

@router.post("/custom-requests", status_code=201)
def create_request(body: CustomRequestCreate, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    req = svc.create_request(session, user, body.customization_id, body.tailor_id,
                             body.delivery_address_id)
    session.commit()
    return ok(svc.request_out(session, req, {"buyer"}))


@router.get("/custom-requests")
def list_requests(as_: str = Query(default="buyer", alias="as", pattern="^(buyer|merchant|tailor)$"),
                  limit: int = Query(default=20, ge=1, le=100),
                  cursor: str | None = Query(default=None), user: User = Depends(current_user),
                  session: Session = Depends(get_session)):
    stmt = select(CustomRequest)
    if as_ == "buyer":
        stmt = stmt.where(CustomRequest.buyer_id == user.id)
    elif as_ == "merchant":
        profile = session.scalar(select(MerchantProfile).where(MerchantProfile.user_id == user.id))
        if profile is None:
            raise Forbidden("Merchant account required")
        stmt = stmt.where(CustomRequest.merchant_id == profile.id)
    else:
        profile = session.scalar(select(TailorProfile).where(TailorProfile.user_id == user.id))
        if profile is None:
            raise Forbidden("Tailor account required")
        stmt = stmt.where(CustomRequest.tailor_id == profile.id)
    page = paginate(session, CustomRequest, stmt, limit=limit, cursor=cursor)
    return ok({"items": [svc.request_out(session, r, {as_}) for r in page["items"]],
               "next_cursor": page["next_cursor"]})


@router.get("/custom-requests/{req_id}")
def get_request(req_id: uuid.UUID, user: User = Depends(current_user),
                session: Session = Depends(get_session)):
    req, roles = svc.get_for(session, user, req_id)
    return ok(svc.request_out(session, req, roles))


@router.patch("/custom-requests/{req_id}")
def update_request(req_id: uuid.UUID, body: CustomRequestUpdate, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    req, roles = _req(session, user, req_id, {"buyer"})
    svc.update_request(session, user, req, tailor_id=body.tailor_id,
                       address_id=body.delivery_address_id)
    session.commit()
    return ok(svc.request_out(session, req, roles))


@router.post("/custom-requests/{req_id}/submit")
def submit_request(req_id: uuid.UUID, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    req, roles = _req(session, user, req_id, {"buyer"})
    svc.submit_request(session, user, req)
    session.commit()
    return ok(svc.request_out(session, req, roles))


@router.post("/custom-requests/{req_id}/withdraw")
def withdraw_request(req_id: uuid.UUID, user: User = Depends(current_user),
                     session: Session = Depends(get_session)):
    req, roles = _req(session, user, req_id, {"buyer"})
    svc.withdraw_request(session, user, req)
    session.commit()
    return ok(svc.request_out(session, req, roles))


# ----- partner validation -----

@router.post("/custom-requests/{req_id}/merchant-confirmation")
def merchant_confirmation(req_id: uuid.UUID, body: MerchantDecisionIn,
                          user: User = Depends(current_user),
                          session: Session = Depends(get_session)):
    req, _ = _req(session, user, req_id, {"merchant"})
    svc.merchant_decide(session, user, req, body.decision, body.reason)
    session.commit()
    return ok(svc.request_out(session, req, {"merchant"}))


@router.post("/custom-requests/{req_id}/tailor-decision")
def tailor_decision(req_id: uuid.UUID, body: TailorDecisionIn, user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
    req, roles = _req(session, user, req_id, {"tailor"})
    svc.tailor_decide(session, user, req, body.action, body.reason)
    session.commit()
    return ok(svc.request_out(session, req, roles))


@router.post("/custom-requests/{req_id}/production-spec", status_code=201)
def production_spec(req_id: uuid.UUID, body: SpecIn, user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
    req, _ = _req(session, user, req_id, {"tailor"})
    spec = svc.issue_spec(session, user, req, body.model_dump(mode="json"))
    session.commit()
    return ok({"id": spec.id, "revision": spec.revision, "status": spec.status,
               "specification": spec.spec})


@router.post("/custom-requests/{req_id}/quotes", status_code=201)
def issue_quote(req_id: uuid.UUID, body: QuoteIssueIn, user: User = Depends(current_user),
                session: Session = Depends(get_session)):
    req, _ = _req(session, user, req_id, {"tailor"})
    quote = svc.issue_quote(session, user, req, body.spec_id, body.expires_in_hours)
    session.commit()
    return ok(svc.quote_out(session, quote))


@router.get("/custom-requests/{req_id}/quotes")
def list_quotes(req_id: uuid.UUID, user: User = Depends(current_user),
                session: Session = Depends(get_session)):
    req, _ = _req(session, user, req_id, {"buyer", "tailor", "admin"})
    rows = session.scalars(select(Quote).where(Quote.request_id == req.id)
                           .order_by(Quote.revision.desc()))
    return ok([svc.quote_out(session, q) for q in rows])


@router.get("/quotes/{quote_id}")
def get_quote(quote_id: uuid.UUID, user: User = Depends(current_user),
              session: Session = Depends(get_session)):
    quote = session.get(Quote, quote_id)
    if quote is None:
        raise NotFound("Quote not found")
    _req(session, user, quote.request_id, {"buyer", "tailor", "admin"})
    return ok(svc.quote_out(session, quote))


@router.post("/quotes/{quote_id}/accept")
def accept_quote(quote_id: uuid.UUID, body: QuoteAcceptIn,
                 key: str = Depends(require_idempotency_key), user: User = Depends(current_user),
                 session: Session = Depends(get_session)):
    quote = session.get(Quote, quote_id)
    if quote is None:
        raise NotFound("Quote not found")
    _req(session, user, quote.request_id, {"buyer"})
    commerce_svc.expire_holds(session)
    session.commit()

    def run() -> tuple[int, dict]:
        payment = orders_svc.accept_quote(
            session, user, quote, expected_quote_revision=body.expected_quote_revision,
            acknowledged_visual_reference=body.acknowledged_visual_reference,
            delivery_address_id=body.delivery_address_id)
        data = {"payment": {"id": payment.id, "status": payment.status,
                            "amount_idr": payment.amount_idr},
                "quote": svc.quote_out(session, quote),
                "simulation_notice": commerce_svc.SIMULATION_NOTICE}
        return 200, jsonable_encoder(ok(data))

    status, payload = run_idempotent(
        session, user_id=user.id, key=key, method="POST", path=f"/quotes/{quote_id}/accept",
        body=body.model_dump_json().encode(), fn=run)
    session.commit()
    return JSONResponse(payload, status_code=status)


# ----- fulfilment -----

def _order_access(session: Session, user: User, order_id: uuid.UUID, allowed: set[str]):
    order, roles = commerce_svc.get_order_for(session, user, order_id)
    if not roles & allowed:
        raise Forbidden()
    return order, roles


@router.post("/orders/{order_id}/fabric-inspection", status_code=201)
def fabric_inspection(order_id: uuid.UUID, body: InspectionIn, user: User = Depends(current_user),
                      session: Session = Depends(get_session)):
    order, roles = _order_access(session, user, order_id, {"tailor"})
    inspection = orders_svc.record_inspection(
        session, user, order, roles, passed=body.passed,
        measured_width_cm=body.measured_width_cm, measured_length_m=body.measured_length_m,
        condition=body.condition, notes=body.notes)
    session.commit()
    return ok({"id": inspection.id, "passed": inspection.passed, "order_status": order.status})


def _amendment_out(a: OrderAmendment) -> dict:
    return {"id": a.id, "reason": a.reason, "changes": a.changes,
            "price_delta_idr": a.price_delta_idr, "status": a.status, "created_at": a.created_at,
            "decided_at": a.decided_at,
            "note": "Order yang sudah dibayar tidak diubah diam-diam; perubahan hanya lewat amandemen."}


@router.post("/orders/{order_id}/amendments", status_code=201)
def propose_amendment(order_id: uuid.UUID, body: AmendmentIn, user: User = Depends(current_user),
                      session: Session = Depends(get_session)):
    order, _ = _order_access(session, user, order_id, {"buyer", "merchant", "tailor"})
    amendment = orders_svc.propose_amendment(session, user, order, body.reason, body.changes,
                                             body.price_delta_idr)
    session.commit()
    return ok(_amendment_out(amendment))


@router.get("/orders/{order_id}/amendments")
def list_amendments(order_id: uuid.UUID, user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
    order, _ = _order_access(session, user, order_id, {"buyer", "merchant", "tailor", "admin"})
    rows = session.scalars(select(OrderAmendment).where(OrderAmendment.order_id == order.id)
                           .order_by(OrderAmendment.created_at))
    return ok([_amendment_out(a) for a in rows])


@router.post("/orders/{order_id}/amendments/{amendment_id}/decision")
def decide_amendment(order_id: uuid.UUID, amendment_id: uuid.UUID, body: AmendmentDecision,
                     user: User = Depends(current_user), session: Session = Depends(get_session)):
    order, _ = _order_access(session, user, order_id, {"buyer"})
    amendment = orders_svc.decide_amendment(
        session, user, order, orders_svc.get_amendment(session, order, amendment_id), body.decision)
    session.commit()
    return ok(_amendment_out(amendment))


