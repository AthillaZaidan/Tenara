import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.config import settings
from app.core.errors import (
    AppValidationError,
    Forbidden,
    InvalidTransition,
    NotFound,
    PaymentExpired,
    StaleRevision,
)
from app.models import (
    DemoPayment,
    FabricInspection,
    FabricListing,
    FabricStockUnit,
    MerchantProfile,
    Order,
    OrderAmendment,
    Quote,
    SettlementEntry,
    Shipment,
    StockReservation,
    TailorProfile,
    User,
)
from app.models.custom import CustomRequest
from app.services import audit
from app.services import commerce as commerce_svc
from app.services import custom_requests as req_svc
from app.services.pricing import commission


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- acceptance + payment ----------

def accept_quote(session, buyer: User, quote: Quote, *, expected_quote_revision: int,
                 acknowledged_visual_reference: bool, delivery_address_id: uuid.UUID):
    """Validate everything the PRD requires, hold the fabric and open a pending demo payment."""
    req = session.get(CustomRequest, quote.request_id)
    if not acknowledged_visual_reference:
        raise AppValidationError("Konfirmasikan bahwa pratinjau hanya referensi visual",
                                 field="acknowledged_visual_reference")
    latest = session.scalar(select(Quote.revision).where(Quote.request_id == req.id)
                            .order_by(Quote.revision.desc()).limit(1))
    if quote.revision != expected_quote_revision or quote.revision != latest:
        raise StaleRevision("Hanya revisi quote terbaru yang dapat disetujui")
    status = req_svc.effective_quote_status(quote)
    if status != "issued":
        raise InvalidTransition(f"Quote is {status}")
    if req.status != "awaiting_buyer" or req.revision != quote.request_revision:
        raise StaleRevision("Permintaan berubah setelah quote ini diterbitkan")
    view = req_svc.quote_out(session, quote)
    if view["stale_reasons"]:
        raise StaleRevision("Desain/ukuran berubah setelah quote: " + ", ".join(view["stale_reasons"]))
    if str(delivery_address_id) != req.address.get("id"):
        raise AppValidationError("Alamat tidak sesuai dengan permintaan", field="delivery_address_id")
    merchant, tailor = session.get(MerchantProfile, req.merchant_id), session.get(TailorProfile, req.tailor_id)
    if merchant.status != "active" or tailor.status != "active":
        raise AppValidationError("Salah satu mitra tidak lagi aktif", field="request")
    pending = session.scalar(select(DemoPayment).where(
        DemoPayment.quote_id == quote.id, DemoPayment.status == "pending"))
    if pending is not None:
        return pending
    listing = session.get(FabricListing, req.listing_id)
    qty = Decimal(view["specification"]["fabric"]["purchase_quantity"])
    reservation = StockReservation(
        listing_id=listing.id, quote_id=quote.id, quantity=qty, allocations=[],
        expires_at=_now() + timedelta(minutes=settings.hold_minutes))
    session.add(reservation)
    session.flush()
    reservation.allocations = commerce_svc.allocate(session, listing, qty, reservation.id)
    payment = DemoPayment(quote_id=quote.id, amount_idr=quote.total_idr, status="pending")
    session.add(payment)
    session.flush()
    audit.record(session, actor=buyer, action="quote.accepted_pending_payment",
                 target_type="quote", target_id=quote.id, metadata={"total_idr": quote.total_idr})
    return payment


def complete_quote_payment(session, buyer: User, payment: DemoPayment, outcome: str) -> Order | None:
    quote = session.get(Quote, payment.quote_id)
    if payment.status == "succeeded":
        if outcome == "succeeded":
            return session.scalar(select(Order).where(Order.id == payment.order_id))
        raise InvalidTransition("Payment already succeeded")
    if payment.status == "expired":
        raise PaymentExpired()
    if payment.status != "pending":
        raise InvalidTransition(f"Payment is already {payment.status}")
    reservation = session.scalar(select(StockReservation).where(
        StockReservation.quote_id == quote.id, StockReservation.status == "held").with_for_update())
    if reservation is None or reservation.expires_at <= _now():
        raise PaymentExpired()
    now = _now()
    if outcome == "failed":
        commerce_svc._release(session, reservation, "released")
        payment.status, payment.resolved_at = "failed", now
        session.flush()
        audit.record(session, actor=buyer, action="payment.failed", target_type="demo_payment",
                     target_id=payment.id)
        return None

    req = session.get(CustomRequest, quote.request_id)
    spec = req_svc.quote_out(session, quote)["specification"]
    lines = req_svc.quote_lines(session, quote)
    merchant, tailor = session.get(MerchantProfile, req.merchant_id), session.get(TailorProfile, req.tailor_id)
    listing = session.get(FabricListing, req.listing_id)
    snapshot = {
        "quote": {"id": str(quote.id), "revision": quote.revision, "total_idr": quote.total_idr,
                  "lines": [{"kind": ln.kind, "description": ln.description,
                             "amount_idr": ln.amount_idr, "owner": ln.owner} for ln in lines],
                  "commission": quote.commission},
        "specification": spec, "design_revision": quote.design_revision,
        "measurements_cm": req.snapshot["measurements_cm"], "template": req.snapshot["template"],
        "listing": {**req.snapshot["listing"], "title": listing.title},
        "merchant": {"id": str(merchant.id), "shop_name": merchant.shop_name, "city": merchant.city,
                     "province": merchant.province},
        "tailor": {"id": str(tailor.id), "shop_name": tailor.shop_name, "city": tailor.city,
                   "province": tailor.province},
        "address": req.address, "visual_reference_acknowledged": True, "simulated": True,
    }
    order = Order(kind="custom", buyer_id=buyer.id, merchant_id=merchant.id, tailor_id=tailor.id,
                  listing_id=listing.id, request_id=req.id, status="confirmed", snapshot=snapshot,
                  total_idr=quote.total_idr)
    session.add(order)
    session.flush()
    commerce_svc._commit_reservation(session, reservation, order.id)
    payment.status, payment.resolved_at, payment.order_id = "succeeded", now, order.id
    quote.status, quote.accepted_at = "accepted", now
    req.status = "converted_to_order"

    leg_cost = {ln.kind: ln.amount_idr for ln in lines}
    session.add(Shipment(order_id=order.id, leg="merchant_to_tailor",
                         shipping_idr=leg_cost.get("shipping_leg_1", 0)))
    session.add(Shipment(order_id=order.id, leg="tailor_to_buyer",
                         shipping_idr=leg_cost.get("shipping_leg_2", 0)))
    gross = {"merchant": 0, "tailor": 0}
    for ln in lines:
        if ln.owner in gross:
            gross[ln.owner] += ln.amount_idr
    for role, user_id, bps_key in (("merchant", merchant.user_id, "merchant_fabric_bps"),
                                   ("tailor", tailor.user_id, "tailoring_bps")):
        bps = quote.commission[bps_key]
        comm = commission(gross[role], bps)
        session.add(SettlementEntry(order_id=order.id, party_user_id=user_id, party_role=role,
                                    kind="sale", gross_idr=gross[role], commission_bps=bps,
                                    commission_idr=comm, net_idr=gross[role] - comm,
                                    created_at=_now()))
    commerce_svc._event(session, order, buyer, "order_confirmed", to_status="confirmed",
                        simulated=True, note="Pembayaran demo berhasil")
    session.flush()
    audit.record(session, actor=buyer, action="payment.succeeded", target_type="demo_payment",
                 target_id=payment.id, metadata={"order_id": str(order.id), "kind": "custom"})
    return order


# ---------- fulfilment ----------

# event -> (allowed roles, from statuses, to status, shipment leg effect)
TRANSITIONS = {
    "start_preparing": ({"merchant"}, ("confirmed",), "fabric_preparing", None),
    "dispatch_to_tailor": ({"merchant"}, ("fabric_preparing",), "shipped_to_tailor",
                           ("merchant_to_tailor", "shipped")),
    "receive_fabric": ({"tailor"}, ("shipped_to_tailor",), "received_by_tailor",
                       ("merchant_to_tailor", "delivered")),
    "begin_production": ({"tailor"}, ("inspection_passed",), "in_production", None),
    "complete_production": ({"tailor"}, ("in_production",), "quality_check", None),
    "dispatch_finished": ({"tailor"}, ("quality_check",), "shipped_to_buyer",
                          ("tailor_to_buyer", "shipped")),
    "simulate_delivery": ({"admin"}, ("shipped_to_buyer",), "delivered",
                          ("tailor_to_buyer", "delivered")),
    "confirm_receipt": ({"buyer"}, ("delivered",), "completed", None),
    "resolve_issue": ({"admin"}, ("inspection_issue",), "received_by_tailor", None),
    "fail_fulfillment": ({"admin"}, ("inspection_issue",), "failed_fulfillment", None),
    "cancel": ({"merchant", "tailor", "admin"}, ("confirmed", "fabric_preparing"), "cancelled", None),
}
NOTE_REQUIRED = {"complete_production", "resolve_issue", "fail_fulfillment", "cancel"}
SIMULATED = {"dispatch_to_tailor", "receive_fabric", "dispatch_finished", "simulate_delivery",
             "fail_fulfillment", "cancel"}


def _reverse_settlement(session, order: Order, note: str) -> None:
    for sale in list(session.scalars(select(SettlementEntry).where(
            SettlementEntry.order_id == order.id, SettlementEntry.kind == "sale"))):
        session.add(SettlementEntry(
            order_id=order.id, party_user_id=sale.party_user_id, party_role=sale.party_role,
            kind="adjustment", gross_idr=-sale.gross_idr, commission_bps=sale.commission_bps,
            commission_idr=-sale.commission_idr, net_idr=-sale.net_idr, note=note,
            created_at=_now()))


def _refund(session, order: Order) -> None:
    payment = session.scalar(select(DemoPayment).where(DemoPayment.order_id == order.id))
    if payment is not None:
        payment.status, payment.resolved_at = "refund_recorded", _now()


def _restore_stock(session, order: Order) -> None:
    listing = session.get(FabricListing, order.listing_id)
    qty = Decimal(order.snapshot["specification"]["fabric"]["purchase_quantity"])
    unit = (FabricStockUnit(listing_id=listing.id, length_m=qty, quantity=1)
            if listing.selling_unit == "meter"
            else FabricStockUnit(listing_id=listing.id, length_m=None, quantity=int(qty)))
    session.add(unit)
    session.flush()
    commerce_svc._movement(session, listing.id, unit.id, unit.quantity, "restore",
                           length_m=unit.length_m, order_id=order.id)


def apply_custom_event(session, user: User, order: Order, roles: set[str], event: str,
                       note: str | None) -> Order:
    if event not in TRANSITIONS:
        raise AppValidationError("Unknown event for this order", field="event")
    allowed, from_states, to_status, leg = TRANSITIONS[event]
    if not roles & allowed:
        raise Forbidden()
    if order.status not in from_states:
        raise InvalidTransition(f"Cannot {event} an order that is {order.status}")
    if event in NOTE_REQUIRED and not note:
        raise AppValidationError("A note is required for this action", field="note")
    previous = order.status
    if leg is not None:
        shipment = session.scalar(select(Shipment).where(Shipment.order_id == order.id,
                                                         Shipment.leg == leg[0]))
        shipment.status = leg[1]
        if leg[1] == "shipped":
            shipment.shipped_at = _now()
            shipment.tracking_no = f"DEMO-{uuid.uuid4().hex[:8].upper()}"
        else:
            shipment.delivered_at = _now()
    if event == "cancel":
        _restore_stock(session, order)
        _refund(session, order)
        _reverse_settlement(session, order, "Pembatalan sebelum fabric dikirim (simulasi)")
    elif event == "fail_fulfillment":
        _refund(session, order)  # fabric may already be cut: it is not restored to stock
        _reverse_settlement(session, order, "Fulfillment gagal (simulasi)")
    order.status = to_status
    commerce_svc._event(session, order, user, event, from_status=previous, to_status=to_status,
                        simulated=event in SIMULATED, note=note)
    session.flush()
    audit.record(session, actor=user, action=f"order.{event}", target_type="order",
                 target_id=order.id, metadata={"from": previous, "to": to_status})
    return order


def record_inspection(session, user: User, order: Order, roles: set[str], *, passed: bool,
                      measured_width_cm, measured_length_m, condition: str,
                      notes: str | None) -> FabricInspection:
    if order.kind != "custom":
        raise AppValidationError("Only custom orders have a fabric inspection", field="order")
    if "tailor" not in roles:
        raise Forbidden()
    if order.status != "received_by_tailor":
        raise InvalidTransition(f"Fabric can only be inspected after receipt (order is {order.status})")
    if not passed and not notes:
        raise AppValidationError("Notes are required when the inspection fails", field="notes")
    inspection = FabricInspection(order_id=order.id, passed=passed,
                                  measured_width_cm=measured_width_cm,
                                  measured_length_m=measured_length_m, condition=condition,
                                  notes=notes, created_by=user.id)
    session.add(inspection)
    previous = order.status
    order.status = "inspection_passed" if passed else "inspection_issue"
    commerce_svc._event(session, order, user, "fabric_inspection", from_status=previous,
                        to_status=order.status, note=notes)
    session.flush()
    audit.record(session, actor=user, action="order.fabric_inspection", target_type="order",
                 target_id=order.id, metadata={"passed": passed})
    return inspection


# ---------- amendments ----------

def propose_amendment(session, user: User, order: Order, reason: str, changes: dict,
                      price_delta_idr: int) -> OrderAmendment:
    if order.kind != "custom":
        raise AppValidationError("Amendments apply to custom orders", field="order")
    amendment = OrderAmendment(order_id=order.id, proposed_by=user.id, reason=reason,
                               changes=changes, price_delta_idr=price_delta_idr)
    session.add(amendment)
    session.flush()
    audit.record(session, actor=user, action="order.amendment_proposed", target_type="order",
                 target_id=order.id, metadata={"amendment_id": str(amendment.id)})
    return amendment


def decide_amendment(session, user: User, order: Order, amendment: OrderAmendment,
                     decision: str) -> OrderAmendment:
    if order.buyer_id != user.id:
        raise Forbidden("Only the buyer can approve or reject an amendment")
    if amendment.status != "proposed":
        raise InvalidTransition(f"Amendment is already {amendment.status}")
    amendment.status = "approved" if decision == "approve" else "rejected"
    amendment.decided_at = _now()
    session.flush()  # the approved order snapshot itself is never edited
    audit.record(session, actor=user, action=f"order.amendment_{amendment.status}",
                 target_type="order", target_id=order.id,
                 metadata={"amendment_id": str(amendment.id), "price_delta_idr": amendment.price_delta_idr})
    return amendment


def get_amendment(session, order: Order, amendment_id: uuid.UUID) -> OrderAmendment:
    amendment = session.get(OrderAmendment, amendment_id)
    if amendment is None or amendment.order_id != order.id:
        raise NotFound("Amendment not found")
    return amendment


