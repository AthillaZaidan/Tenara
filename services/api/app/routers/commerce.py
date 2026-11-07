import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import current_user, require_role
from app.core.errors import Forbidden
from app.core.pagination import paginate
from app.core.responses import ok
from app.db.base import get_session
from app.models import CommissionRule, DeliveryAddress, MerchantProfile, Order, User
from app.schemas.commerce import (
    AddressIn,
    CheckoutConfirm,
    CheckoutCreate,
    CommissionRuleIn,
    OrderEventIn,
    PaymentComplete,
)
from app.services import commerce as svc
from app.services.idempotency import require_idempotency_key, run_idempotent

router = APIRouter(tags=["commerce"])


def _sweep(session: Session) -> None:
    """Release expired payment holds and persist it before any request logic runs."""
    svc.expire_holds(session)
    session.commit()


def _idempotent(session: Session, user: User, key: str, path: str, body: BaseModel,
                fn: Callable[[], tuple[int, dict]]) -> JSONResponse:
    status, payload = run_idempotent(session, user_id=user.id, key=key, method="POST", path=path,
                                     body=body.model_dump_json().encode(), fn=fn)
    session.commit()
    return JSONResponse(payload, status_code=status)


# ----- addresses -----

@router.post("/addresses", status_code=201)
def create_address(body: AddressIn, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    address = svc.create_address(session, user, body.model_dump())
    session.commit()
    return ok(svc.address_out(address))


@router.get("/addresses")
def list_addresses(user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = session.scalars(select(DeliveryAddress).where(DeliveryAddress.user_id == user.id)
                           .order_by(DeliveryAddress.created_at))
    return ok([svc.address_out(a) for a in rows])


@router.delete("/addresses/{address_id}")
def delete_address(address_id: uuid.UUID, user: User = Depends(current_user),
                   session: Session = Depends(get_session)):
    session.delete(svc.owned_address(session, user, address_id))
    session.commit()
    return ok({"deleted": str(address_id)})


# ----- fabric checkout -----

@router.post("/fabric-checkouts", status_code=201)
def create_checkout(body: CheckoutCreate, user: User = Depends(current_user),
                    session: Session = Depends(get_session)):
    _sweep(session)
    checkout = svc.create_checkout(session, user, body.listing_id, body.quantity,
                                   body.delivery_address_id)
    session.commit()
    return ok(svc.checkout_out(session, checkout))


@router.get("/fabric-checkouts/{checkout_id}")
def get_checkout(checkout_id: uuid.UUID, user: User = Depends(current_user),
                 session: Session = Depends(get_session)):
    _sweep(session)
    return ok(svc.checkout_out(session, svc.owned_checkout(session, user, checkout_id)))


@router.post("/fabric-checkouts/{checkout_id}/confirm")
def confirm_checkout(checkout_id: uuid.UUID, body: CheckoutConfirm,
                     key: str = Depends(require_idempotency_key),
                     user: User = Depends(current_user), session: Session = Depends(get_session)):
    _sweep(session)
    checkout = svc.owned_checkout(session, user, checkout_id)

    def run() -> tuple[int, dict]:
        confirmed, _payment = svc.confirm_checkout(session, user, checkout, body.expected_total_idr)
        return 200, jsonable_encoder(ok(svc.checkout_out(session, confirmed)))

    return _idempotent(session, user, key, f"/fabric-checkouts/{checkout_id}/confirm", body, run)


@router.post("/demo-payments/{payment_id}/complete")
def complete_payment(payment_id: uuid.UUID, body: PaymentComplete,
                     key: str = Depends(require_idempotency_key),
                     user: User = Depends(current_user), session: Session = Depends(get_session)):
    _sweep(session)
    payment = svc.owned_payment(session, user, payment_id)

    def run() -> tuple[int, dict]:
        order = svc.complete_payment(session, user, payment, body.outcome)
        data = {"payment": {"id": payment.id, "status": payment.status,
                            "amount_idr": payment.amount_idr},
                "order": svc.order_out(session, order) if order else None,
                "simulation_notice": svc.SIMULATION_NOTICE}
        return 200, jsonable_encoder(ok(data))

    return _idempotent(session, user, key, f"/demo-payments/{payment_id}/complete", body, run)


# ----- orders -----

@router.get("/orders")
def list_orders(as_: str = Query(default="buyer", alias="as", pattern="^(buyer|merchant|admin)$"),
                status: str | None = Query(default=None),
                limit: int = Query(default=20, ge=1, le=100),
                cursor: str | None = Query(default=None),
                user: User = Depends(current_user), session: Session = Depends(get_session)):
    stmt = select(Order)
    if as_ == "buyer":
        stmt = stmt.where(Order.buyer_id == user.id)
    elif as_ == "merchant":
        profile = session.scalar(select(MerchantProfile).where(MerchantProfile.user_id == user.id))
        if profile is None:
            raise Forbidden("Merchant account required")
        stmt = stmt.where(Order.merchant_id == profile.id)
    else:
        require_role("admin")(user)
    if status:
        stmt = stmt.where(Order.status == status)
    page = paginate(session, Order, stmt, limit=limit, cursor=cursor)
    items = [{"id": o.id, "kind": o.kind, "status": o.status, "total_idr": o.total_idr,
              "created_at": o.created_at, "title": o.snapshot.get("listing", {}).get("title")}
             for o in page["items"]]
    return ok({"items": items, "next_cursor": page["next_cursor"]})


@router.get("/orders/{order_id}")
def get_order(order_id: uuid.UUID, user: User = Depends(current_user),
              session: Session = Depends(get_session)):
    order, _roles = svc.get_order_for(session, user, order_id)
    return ok(svc.order_out(session, order))


@router.post("/orders/{order_id}/events")
def order_event(order_id: uuid.UUID, body: OrderEventIn, user: User = Depends(current_user),
                session: Session = Depends(get_session)):
    order, roles = svc.get_order_for(session, user, order_id)
    svc.apply_event(session, user, order, roles, body.event, body.note)
    session.commit()
    return ok(svc.order_out(session, order))


@router.get("/orders/{order_id}/settlement")
def order_settlement(order_id: uuid.UUID, user: User = Depends(current_user),
                     session: Session = Depends(get_session)):
    order, roles = svc.get_order_for(session, user, order_id)
    return ok(svc.settlement_out(session, user, order, roles))


# ----- admin: commission -----

@router.get("/admin/commission-rules")
def list_rules(user: User = Depends(require_role("admin")), session: Session = Depends(get_session)):
    rows = session.scalars(select(CommissionRule).order_by(CommissionRule.created_at.desc()))
    return ok([{"id": r.id, "applies_to": r.applies_to, "rate_bps": r.rate_bps,
                "active": r.active, "created_at": r.created_at} for r in rows])


@router.post("/admin/commission-rules", status_code=201)
def set_rule(body: CommissionRuleIn, user: User = Depends(require_role("admin")),
             session: Session = Depends(get_session)):
    rule = svc.set_commission_rule(session, user, body.applies_to, body.rate_bps)
    session.commit()
    return ok({"id": rule.id, "applies_to": rule.applies_to, "rate_bps": rule.rate_bps})


