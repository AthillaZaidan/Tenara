import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import (
    AppValidationError,
    Forbidden,
    InsufficientStock,
    InvalidTransition,
    NotFound,
    PaymentExpired,
    StaleRevision,
)
from app.models import (
    CommissionRule,
    DeliveryAddress,
    DemoPayment,
    FabricCheckout,
    FabricListing,
    FabricStockUnit,
    MerchantProfile,
    Order,
    OrderEvent,
    RoleAssignment,
    SettlementEntry,
    Shipment,
    StockMovement,
    StockReservation,
    TailorProfile,
    User,
)
from app.services import audit
from app.services import listings as listings_svc
from app.services.pricing import commission, line_subtotal, validate_quantity
from app.services.shipping import estimate

SIMULATION_NOTICE = ("SIMULASI DEMO: pembayaran, ongkir, pelacakan kurir, dan penyelesaian "
                     "dana bukan transaksi sungguhan.")
MIN_REMAINDER_M = Decimal("0.01")


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- addresses ----------

def create_address(session: Session, user: User, data: dict) -> DeliveryAddress:
    address = DeliveryAddress(user_id=user.id, **data)
    session.add(address)
    session.flush()
    return address


def address_out(a: DeliveryAddress) -> dict:
    return {"id": a.id, "label": a.label, "recipient_name": a.recipient_name, "phone": a.phone,
            "line1": a.line1, "city": a.city, "province": a.province, "postal_code": a.postal_code}


def owned_address(session: Session, user: User, address_id: uuid.UUID) -> DeliveryAddress:
    address = session.get(DeliveryAddress, address_id)
    if address is None or address.user_id != user.id:
        raise NotFound("Address not found")
    return address


# ---------- commission ----------

def commission_bps(session: Session, applies_to: str = "merchant_fabric") -> int:
    rule = session.scalar(select(CommissionRule)
                          .where(CommissionRule.applies_to == applies_to, CommissionRule.active)
                          .order_by(CommissionRule.created_at.desc()).limit(1))
    return rule.rate_bps if rule else settings.default_commission_bps


def set_commission_rule(session: Session, admin: User, applies_to: str, rate_bps: int) -> CommissionRule:
    for old in session.scalars(select(CommissionRule).where(
            CommissionRule.applies_to == applies_to, CommissionRule.active)):
        old.active = False
    rule = CommissionRule(applies_to=applies_to, rate_bps=rate_bps, created_by=admin.id)
    session.add(rule)
    session.flush()
    audit.record(session, actor=admin, action="commission.rule_set", target_type="commission_rule",
                 target_id=rule.id, metadata={"applies_to": applies_to, "rate_bps": rate_bps})
    return rule


# ---------- stock allocation ----------

def _movement(session: Session, listing_id, unit_id, delta, reason, *, length_m=None,
              reservation_id=None, order_id=None) -> None:
    session.add(StockMovement(listing_id=listing_id, unit_id=unit_id, quantity_delta=delta,
                              length_m=length_m, reason=reason, reservation_id=reservation_id,
                              order_id=order_id))


def can_fulfill(session: Session, listing: FabricListing, qty: Decimal) -> bool:
    """Non-locking availability check used for early feedback; allocation re-checks under lock."""
    if listing.selling_unit == "meter":
        return session.scalar(select(FabricStockUnit.id).where(
            FabricStockUnit.listing_id == listing.id, FabricStockUnit.quantity > 0,
            FabricStockUnit.length_m >= qty).limit(1)) is not None
    available = sum(u.quantity for u in session.scalars(select(FabricStockUnit).where(
        FabricStockUnit.listing_id == listing.id, FabricStockUnit.quantity > 0)))
    return available >= int(qty)


def allocate(session: Session, listing: FabricListing, qty: Decimal, reservation_id) -> list[dict]:
    """Take stock out of availability under row locks. Raises InsufficientStock before mutating."""
    if listing.selling_unit == "meter":
        unit = session.scalar(
            select(FabricStockUnit)
            .where(FabricStockUnit.listing_id == listing.id, FabricStockUnit.quantity > 0,
                   FabricStockUnit.length_m >= qty)
            .order_by(FabricStockUnit.length_m, FabricStockUnit.id)  # best fit: least waste
            .limit(1).with_for_update(skip_locked=True))
        if unit is None:
            raise InsufficientStock(f"No continuous piece of at least {qty} m is available")
        unit.quantity -= 1
        _movement(session, listing.id, unit.id, -1, "hold", length_m=unit.length_m,
                  reservation_id=reservation_id)
        return [{"unit_id": str(unit.id), "taken": 1, "source_length_m": str(unit.length_m)}]
    need = int(qty)
    units = list(session.scalars(
        select(FabricStockUnit)
        .where(FabricStockUnit.listing_id == listing.id, FabricStockUnit.quantity > 0)
        .order_by(FabricStockUnit.id).with_for_update(skip_locked=True)))
    if sum(u.quantity for u in units) < need:
        raise InsufficientStock(f"Only {sum(u.quantity for u in units)} piece(s) available")
    allocations = []
    for unit in units:
        take = min(need, unit.quantity)
        if take:
            unit.quantity -= take
            _movement(session, listing.id, unit.id, -take, "hold", reservation_id=reservation_id)
            allocations.append({"unit_id": str(unit.id), "taken": take, "source_length_m": None})
            need -= take
        if not need:
            break
    return allocations


def _release(session: Session, reservation: StockReservation, status: str) -> None:
    for alloc in reservation.allocations:
        unit = session.get(FabricStockUnit, uuid.UUID(alloc["unit_id"]), with_for_update=True)
        if unit is not None:
            unit.quantity += alloc["taken"]
            _movement(session, reservation.listing_id, unit.id, alloc["taken"], "release",
                      reservation_id=reservation.id)
    reservation.status, reservation.resolved_at = status, _now()


def _commit_reservation(session: Session, reservation: StockReservation, order_id) -> None:
    for alloc in reservation.allocations:
        if alloc["source_length_m"] is not None:
            remainder = Decimal(alloc["source_length_m"]) - reservation.quantity
            if remainder >= MIN_REMAINDER_M:
                unit = FabricStockUnit(listing_id=reservation.listing_id, length_m=remainder,
                                       quantity=1)
                session.add(unit)
                session.flush()
                _movement(session, reservation.listing_id, unit.id, 1, "remainder",
                          length_m=remainder, reservation_id=reservation.id, order_id=order_id)
    _movement(session, reservation.listing_id, None, 0, "commit", length_m=reservation.quantity,
              reservation_id=reservation.id, order_id=order_id)
    reservation.status, reservation.resolved_at = "committed", _now()


def expire_holds(session: Session, now: datetime | None = None) -> int:
    """Release holds whose payment window passed. Callers commit afterwards."""
    now = now or _now()
    stale = list(session.scalars(select(StockReservation).where(
        StockReservation.status == "held", StockReservation.expires_at <= now)
        .with_for_update(skip_locked=True)))
    for reservation in stale:
        _release(session, reservation, "expired")
        if reservation.quote_id:
            quote_payment = session.scalar(select(DemoPayment).where(
                DemoPayment.quote_id == reservation.quote_id, DemoPayment.status == "pending"))
            if quote_payment is not None:
                quote_payment.status, quote_payment.resolved_at = "expired", now
        checkout = session.get(FabricCheckout, reservation.checkout_id) if reservation.checkout_id else None
        if checkout is not None and checkout.status == "payment_pending":
            checkout.status = "expired"
            payment = session.scalar(select(DemoPayment).where(DemoPayment.checkout_id == checkout.id))
            if payment is not None and payment.status == "pending":
                payment.status, payment.resolved_at = "expired", now
    session.flush()
    return len(stale)


# ---------- checkout ----------

def _totals(listing: FabricListing, qty: Decimal, address: dict) -> dict:
    subtotal = line_subtotal(listing.price_idr, qty)
    shipping = estimate(listing.city, listing.province, address["city"], address["province"])
    fee = settings.buyer_service_fee_idr
    return {"unit_price_idr": listing.price_idr, "subtotal_idr": subtotal,
            "shipping_idr": shipping, "service_fee_idr": fee, "total_idr": subtotal + shipping + fee}


def create_checkout(session: Session, buyer: User, listing_id: uuid.UUID, qty: Decimal,
                    address_id: uuid.UUID) -> FabricCheckout:
    listing = listings_svc.public_listing(session, listing_id)
    merchant = session.get(MerchantProfile, listing.merchant_id)
    if merchant.user_id == buyer.id:
        raise AppValidationError("You cannot buy your own listing", field="listing_id")
    validate_quantity(listing, qty)
    if not can_fulfill(session, listing, qty):
        raise InsufficientStock("This quantity is not currently available")
    stored = owned_address(session, buyer, address_id)
    address = {**address_out(stored), "id": str(stored.id)}  # JSON-safe snapshot
    checkout = FabricCheckout(buyer_id=buyer.id, listing_id=listing.id, quantity=qty,
                              address=address, **_totals(listing, qty, address))
    session.add(checkout)
    session.flush()
    return checkout


def owned_checkout(session: Session, buyer: User, checkout_id: uuid.UUID) -> FabricCheckout:
    checkout = session.get(FabricCheckout, checkout_id)
    if checkout is None or checkout.buyer_id != buyer.id:
        raise NotFound("Checkout not found")
    return checkout


def checkout_out(session: Session, c: FabricCheckout) -> dict:
    listing = session.get(FabricListing, c.listing_id)
    payment = session.scalar(select(DemoPayment).where(DemoPayment.checkout_id == c.id))
    return {
        "id": c.id, "status": c.status, "listing_id": c.listing_id, "listing_title": listing.title,
        "selling_unit": listing.selling_unit, "quantity": c.quantity,
        "unit_price_idr": c.unit_price_idr, "subtotal_idr": c.subtotal_idr,
        "shipping_idr": c.shipping_idr, "service_fee_idr": c.service_fee_idr,
        "total_idr": c.total_idr, "address": c.address, "expires_at": c.expires_at,
        "payment": {"id": payment.id, "status": payment.status} if payment else None,
        "simulation_notice": SIMULATION_NOTICE,
    }


def confirm_checkout(session: Session, buyer: User, checkout: FabricCheckout,
                     expected_total_idr: int) -> tuple[FabricCheckout, DemoPayment]:
    """Recheck price/stock, hold stock atomically and open a pending demo payment."""
    if checkout.status != "review":
        raise InvalidTransition(f"Checkout is already {checkout.status}")
    listing = listings_svc.public_listing(session, checkout.listing_id)
    validate_quantity(listing, checkout.quantity)
    current = _totals(listing, checkout.quantity, checkout.address)
    if current["total_idr"] != expected_total_idr or current["total_idr"] != checkout.total_idr:
        raise StaleRevision(f"Total berubah menjadi {current['total_idr']}; buat tinjauan baru "
                            f"sebelum membayar")
    reservation = StockReservation(
        listing_id=listing.id, checkout_id=checkout.id, quantity=checkout.quantity, allocations=[],
        expires_at=_now() + timedelta(minutes=settings.hold_minutes))
    session.add(reservation)
    session.flush()
    reservation.allocations = allocate(session, listing, checkout.quantity, reservation.id)
    payment = DemoPayment(checkout_id=checkout.id, amount_idr=checkout.total_idr, status="pending")
    session.add(payment)
    checkout.status, checkout.expires_at = "payment_pending", reservation.expires_at
    session.flush()
    audit.record(session, actor=buyer, action="checkout.confirmed", target_type="fabric_checkout",
                 target_id=checkout.id, metadata={"total_idr": checkout.total_idr})
    return checkout, payment


def owned_payment(session: Session, buyer: User, payment_id: uuid.UUID) -> DemoPayment:
    payment = session.get(DemoPayment, payment_id)
    if payment is not None and payment.quote_id:
        from app.models.custom import CustomRequest, Quote

        quote = session.get(Quote, payment.quote_id)
        request = session.get(CustomRequest, quote.request_id)
        if request.buyer_id != buyer.id:
            raise NotFound("Payment not found")
        return payment
    checkout = session.get(FabricCheckout, payment.checkout_id) if payment and payment.checkout_id else None
    if payment is None or checkout is None or checkout.buyer_id != buyer.id:
        raise NotFound("Payment not found")
    return payment


def _event(session: Session, order: Order, actor: User | None, event_type: str, *, from_status=None,
           to_status=None, simulated=False, note=None) -> None:
    session.add(OrderEvent(order_id=order.id, actor_id=actor.id if actor else None,
                           event_type=event_type, from_status=from_status, to_status=to_status,
                           simulated=simulated, note=note, created_at=_now()))


def complete_payment(session: Session, buyer: User, payment: DemoPayment, outcome: str) -> Order | None:
    """Resolve the simulated payment. Returns the new Order on success, otherwise None."""
    checkout = session.get(FabricCheckout, payment.checkout_id)
    if payment.status == "succeeded":
        if outcome == "succeeded":
            return session.scalar(select(Order).where(Order.checkout_id == checkout.id))
        raise InvalidTransition("Payment already succeeded")
    if payment.status == "expired":
        raise PaymentExpired()
    if payment.status != "pending":
        raise InvalidTransition(f"Payment is already {payment.status}")
    reservation = session.scalar(select(StockReservation).where(
        StockReservation.checkout_id == checkout.id, StockReservation.status == "held")
        .with_for_update())
    if reservation is None:
        raise PaymentExpired()
    now = _now()
    if reservation.expires_at <= now:
        raise PaymentExpired()
    if outcome == "failed":
        _release(session, reservation, "released")
        payment.status, payment.resolved_at = "failed", now
        checkout.status = "failed"
        session.flush()
        audit.record(session, actor=buyer, action="payment.failed", target_type="demo_payment",
                     target_id=payment.id)
        return None

    listing = session.get(FabricListing, checkout.listing_id)
    merchant = session.get(MerchantProfile, listing.merchant_id)
    bps = commission_bps(session)
    snapshot = {
        "listing": {"id": str(listing.id), "title": listing.title, "material": listing.material,
                    "selling_unit": listing.selling_unit},
        "merchant": {"id": str(merchant.id), "shop_name": merchant.shop_name,
                     "city": merchant.city, "province": merchant.province},
        "quantity": str(checkout.quantity), "unit_price_idr": checkout.unit_price_idr,
        "subtotal_idr": checkout.subtotal_idr, "shipping_idr": checkout.shipping_idr,
        "service_fee_idr": checkout.service_fee_idr, "total_idr": checkout.total_idr,
        "address": checkout.address, "commission_bps": bps, "simulated": True,
    }
    order = Order(kind="fabric", buyer_id=buyer.id, merchant_id=merchant.id, listing_id=listing.id,
                  checkout_id=checkout.id, status="confirmed", snapshot=snapshot,
                  total_idr=checkout.total_idr)
    session.add(order)
    session.flush()
    _commit_reservation(session, reservation, order.id)
    payment.status, payment.resolved_at, payment.order_id = "succeeded", now, order.id
    checkout.status = "paid"
    session.add(Shipment(order_id=order.id, leg="merchant_to_buyer", shipping_idr=checkout.shipping_idr))
    comm = commission(checkout.subtotal_idr, bps)
    session.add(SettlementEntry(order_id=order.id, party_user_id=merchant.user_id,
                                party_role="merchant", kind="sale",
                                gross_idr=checkout.subtotal_idr, commission_bps=bps,
                                commission_idr=comm, net_idr=checkout.subtotal_idr - comm,
                                created_at=_now()))
    _event(session, order, buyer, "order_confirmed", to_status="confirmed", simulated=True,
           note="Pembayaran demo berhasil")
    session.flush()
    audit.record(session, actor=buyer, action="payment.succeeded", target_type="demo_payment",
                 target_id=payment.id, metadata={"order_id": str(order.id)})
    return order


# ---------- orders ----------

def order_roles_admin(session: Session, user: User) -> bool:
    return session.scalar(select(RoleAssignment.id).where(
        RoleAssignment.user_id == user.id, RoleAssignment.role == "admin",
        RoleAssignment.status == "active")) is not None


def order_roles(session: Session, user: User, order: Order) -> set[str]:
    roles = set()
    if order.buyer_id == user.id:
        roles.add("buyer")
    if order.merchant_id:
        merchant = session.get(MerchantProfile, order.merchant_id)
        if merchant.user_id == user.id:
            roles.add("merchant")
    if order.tailor_id:
        tailor = session.get(TailorProfile, order.tailor_id)
        if tailor.user_id == user.id:
            roles.add("tailor")
    if order_roles_admin(session, user):
        roles.add("admin")
    return roles


def get_order_for(session: Session, user: User, order_id: uuid.UUID) -> tuple[Order, set[str]]:
    order = session.get(Order, order_id)
    roles = order_roles(session, user, order) if order else set()
    if order is None or not roles:
        raise NotFound("Order not found")
    return order, roles


FABRIC_TRANSITIONS = {
    "start_preparing": ({"merchant"}, ("confirmed",), "preparing"),
    "dispatch": ({"merchant"}, ("preparing",), "shipped_to_buyer"),
    "simulate_delivery": ({"admin"}, ("shipped_to_buyer",), "delivered"),
    "confirm_receipt": ({"buyer"}, ("delivered",), "completed"),
    "cancel": ({"merchant", "admin"}, ("confirmed", "preparing"), "cancelled"),
}


def apply_event(session: Session, user: User, order: Order, roles: set[str], event: str,
                note: str | None) -> Order:
    if event == "confirm_receipt":
        from app.services.claims import has_open_claim  # local import: claims depends on commerce

        if has_open_claim(session, order.id):
            raise InvalidTransition("Masih ada klaim terbuka; selesaikan klaim sebelum konfirmasi terima")
    if order.kind == "custom":
        from app.services import custom_orders  # local import: custom_orders depends on commerce

        return custom_orders.apply_custom_event(session, user, order, roles, event, note)
    if order.kind != "fabric" or event not in FABRIC_TRANSITIONS:
        raise AppValidationError("Unknown event for this order", field="event")
    allowed_roles, from_states, to_status = FABRIC_TRANSITIONS[event]
    if not roles & allowed_roles:
        raise Forbidden()
    if order.status not in from_states:
        raise InvalidTransition(f"Cannot {event} an order that is {order.status}")
    if event == "cancel" and not note:
        raise AppValidationError("A reason is required to cancel", field="note")
    previous = order.status
    shipment = session.scalar(select(Shipment).where(
        Shipment.order_id == order.id, Shipment.leg == "merchant_to_buyer"))
    simulated = False
    if event == "dispatch":
        shipment.status, shipment.shipped_at = "shipped", _now()
        shipment.tracking_no = f"DEMO-{uuid.uuid4().hex[:8].upper()}"
        simulated = True
    elif event == "simulate_delivery":
        shipment.status, shipment.delivered_at = "delivered", _now()
        simulated = True
    elif event == "cancel":
        _cancel_fabric(session, order)
        simulated = True
    order.status = to_status
    _event(session, order, user, event, from_status=previous, to_status=to_status,
           simulated=simulated, note=note)
    session.flush()
    audit.record(session, actor=user, action=f"order.{event}", target_type="order",
                 target_id=order.id, metadata={"from": previous, "to": to_status})
    return order


def _cancel_fabric(session: Session, order: Order) -> None:
    """Pre-dispatch cancellation: fabric is untouched, so it returns to stock; money is refunded
    (simulated) and the merchant settlement is reversed."""
    snap = order.snapshot
    listing = session.get(FabricListing, order.listing_id)
    qty = Decimal(snap["quantity"])
    if listing.selling_unit == "meter":
        unit = FabricStockUnit(listing_id=listing.id, length_m=qty, quantity=1)
    else:
        unit = FabricStockUnit(listing_id=listing.id, length_m=None, quantity=int(qty))
    session.add(unit)
    session.flush()
    _movement(session, listing.id, unit.id, unit.quantity, "restore",
              length_m=unit.length_m, order_id=order.id)
    payment = session.scalar(select(DemoPayment).where(DemoPayment.order_id == order.id))
    if payment is not None:
        payment.status, payment.resolved_at = "refund_recorded", _now()
    sale = session.scalar(select(SettlementEntry).where(
        SettlementEntry.order_id == order.id, SettlementEntry.kind == "sale"))
    if sale is not None:
        session.add(SettlementEntry(order_id=order.id, party_user_id=sale.party_user_id,
                                    party_role=sale.party_role, kind="adjustment",
                                    gross_idr=-sale.gross_idr, commission_bps=sale.commission_bps,
                                    commission_idr=-sale.commission_idr, net_idr=-sale.net_idr,
                                    note="Pembatalan sebelum pengiriman (simulasi)",
                                    created_at=_now()))


def _redact_for_merchant(snapshot: dict) -> dict:
    hidden = {"measurements_cm", "address", "design_state"}
    cleaned = {k: v for k, v in snapshot.items() if k not in hidden}
    if "specification" in cleaned:
        cleaned["specification"] = {k: v for k, v in cleaned["specification"].items()
                                    if k not in hidden | {"finished_dimensions_cm"}}
    return cleaned


def order_out(session: Session, order: Order, roles: set[str] | None = None) -> dict:
    events = session.scalars(select(OrderEvent).where(OrderEvent.order_id == order.id)
                             .order_by(OrderEvent.created_at, OrderEvent.id))
    shipments = session.scalars(select(Shipment).where(Shipment.order_id == order.id))
    payment = session.scalar(select(DemoPayment).where(DemoPayment.order_id == order.id))
    return {
        "id": order.id, "kind": order.kind, "status": order.status, "total_idr": order.total_idr,
        "created_at": order.created_at,
        "snapshot": (_redact_for_merchant(order.snapshot)
                     if order.kind == "custom" and roles and roles <= {"merchant"}
                     else order.snapshot),
        "payment": {"status": payment.status, "amount_idr": payment.amount_idr} if payment else None,
        "shipments": [{"leg": s.leg, "status": s.status, "tracking_no": s.tracking_no,
                       "shipped_at": s.shipped_at, "delivered_at": s.delivered_at,
                       "shipping_idr": s.shipping_idr, "simulated": True} for s in shipments],
        "events": [{"type": e.event_type, "from_status": e.from_status, "to_status": e.to_status,
                    "simulated": e.simulated, "note": e.note, "created_at": e.created_at}
                   for e in events],
        "simulation_notice": SIMULATION_NOTICE,
    }


def settlement_out(session: Session, user: User, order: Order, roles: set[str]) -> dict:
    snap = order.snapshot
    out = {"simulation_notice": SIMULATION_NOTICE}
    if "buyer" in roles:
        if order.kind == "custom":
            out["buyer_total"] = {"lines": snap["quote"]["lines"], "total_idr": order.total_idr}
        else:
            out["buyer_total"] = {k: snap[k] for k in ("subtotal_idr", "shipping_idr",
                                                       "service_fee_idr", "total_idr")}
    entries = select(SettlementEntry).where(SettlementEntry.order_id == order.id)
    if "admin" not in roles and roles & {"merchant", "tailor"}:
        entries = entries.where(SettlementEntry.party_user_id == user.id)
    if roles & {"admin", "merchant", "tailor"}:
        rows = session.scalars(entries.order_by(SettlementEntry.created_at, SettlementEntry.id))
        out["entries"] = [{"party_role": r.party_role, "kind": r.kind, "gross_idr": r.gross_idr,
                           "commission_bps": r.commission_bps, "commission_idr": r.commission_idr,
                           "net_idr": r.net_idr, "note": r.note} for r in rows]
    return out
