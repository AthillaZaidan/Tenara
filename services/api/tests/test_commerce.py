import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import (
    DemoPayment,
    FabricListing,
    FabricStockUnit,
    StockReservation,
)
from app.services.commerce import expire_holds
from app.services.pricing import commission, line_subtotal

API = "/api/v1"
ADDRESS = {"label": "Rumah", "recipient_name": "Budi", "phone": "0812345", "line1": "Jl. Mawar 1",
           "city": "Jakarta", "province": "DKI Jakarta"}


@pytest.fixture
def entry(published_entry):
    return published_entry()


@pytest.fixture
def make_listing(session, make_partner, entry):
    def _make(unit="meter", price=100_000, stock=((Decimal(3), 1),), merchant=None, status="published",
              **extra):
        if unit == "meter":
            extra.setdefault("min_quantity", Decimal(1))
            extra.setdefault("quantity_increment", Decimal("0.5"))
        user, profile = merchant or make_partner("merchant", shop=f"Toko {uuid.uuid4().hex[:5]}",
                                                 city="Bandung", province="Jawa Barat")
        listing = FabricListing(merchant_id=profile.id, entry_id=entry.id, title="Kain uji",
                                selling_unit=unit, price_idr=price, material="katun",
                                usable_width_cm=110 if unit == "meter" else None, city=profile.city,
                                province=profile.province, status=status, **extra)
        session.add(listing)
        session.flush()
        for length, qty in stock:
            session.add(FabricStockUnit(listing_id=listing.id, length_m=None if unit == "piece" else length,
                                        quantity=qty))
        session.flush()
        return listing, user, profile

    return _make


@pytest.fixture
def buyer(make_user):
    return make_user("buyer@example.com")


@pytest.fixture
def address(client, buyer, auth_header):
    r = client.post(f"{API}/addresses", headers=auth_header(buyer), json=ADDRESS)
    assert r.status_code == 201
    return r.json()["data"]


@pytest.fixture
def admin(make_user):
    return make_user("admin@example.com", roles=(("admin", "active"),))


def _checkout(client, user, listing, address, qty, auth_header):
    return client.post(f"{API}/fabric-checkouts", headers=auth_header(user),
                       json={"listing_id": str(listing.id), "quantity": str(qty),
                             "delivery_address_id": address["id"]})


def _confirm(client, user, checkout, auth_header, key="k-confirm", total=None):
    return client.post(f"{API}/fabric-checkouts/{checkout['id']}/confirm",
                       headers={**auth_header(user), "Idempotency-Key": key},
                       json={"expected_total_idr": total or checkout["total_idr"]})


def _pay(client, user, payment_id, auth_header, outcome="succeeded", key="k-pay"):
    return client.post(f"{API}/demo-payments/{payment_id}/complete",
                       headers={**auth_header(user), "Idempotency-Key": key},
                       json={"outcome": outcome})


def _units(session, listing):
    session.expire_all()
    return sorted((u.length_m, u.quantity) for u in session.scalars(
        select(FabricStockUnit).where(FabricStockUnit.listing_id == listing.id)))


def _buy(client, buyer, listing, address, auth_header, qty="1.5"):
    co = _checkout(client, buyer, listing, address, qty, auth_header).json()["data"]
    conf = _confirm(client, buyer, co, auth_header).json()["data"]
    paid = _pay(client, buyer, conf["payment"]["id"], auth_header).json()["data"]
    return paid["order"]


# ---------- pricing ----------

def test_commission_rounds_half_up_and_is_symmetric():
    assert commission(33_333, 500) == 1667  # 1666.65
    assert commission(10_000, 250) == 250
    assert commission(10_010, 250) == 250  # 250.25
    assert commission(-33_333, 500) == -1667
    assert commission(0, 500) == 0


def test_line_subtotal_rounds_half_up():
    assert line_subtotal(10_001, Decimal("0.5")) == 5001  # 5000.5
    assert line_subtotal(100_000, Decimal("1.5")) == 150_000


# ---------- checkout review ----------

def test_review_shows_itemised_simulated_totals(client, buyer, address, make_listing, auth_header):
    listing, *_ = make_listing()
    r = _checkout(client, buyer, listing, address, "1.5", auth_header)
    assert r.status_code == 201
    c = r.json()["data"]
    assert (c["subtotal_idr"], c["shipping_idr"], c["service_fee_idr"], c["total_idr"]) == (
        150_000, 35_000, 0, 185_000)
    assert c["status"] == "review" and "SIMULASI" in c["simulation_notice"]


def test_shipping_is_cheaper_within_province(client, buyer, auth_header, make_listing):
    listing, *_ = make_listing()
    local = client.post(f"{API}/addresses", headers=auth_header(buyer),
                        json={**ADDRESS, "city": "Cimahi", "province": "Jawa Barat"}).json()["data"]
    assert _checkout(client, buyer, listing, local, "1", auth_header).json()["data"]["shipping_idr"] == 20_000
    same_city = client.post(f"{API}/addresses", headers=auth_header(buyer),
                            json={**ADDRESS, "city": "Bandung", "province": "Jawa Barat"}).json()["data"]
    assert _checkout(client, buyer, listing, same_city, "1", auth_header).json()["data"]["shipping_idr"] == 10_000


def test_service_fee_is_added_when_configured(client, buyer, address, make_listing, auth_header, monkeypatch):
    monkeypatch.setattr("app.services.commerce.settings.buyer_service_fee_idr", 2500)
    listing, *_ = make_listing()
    c = _checkout(client, buyer, listing, address, "1", auth_header).json()["data"]
    assert c["service_fee_idr"] == 2500 and c["total_idr"] == 100_000 + 35_000 + 2500


@pytest.mark.parametrize("qty,field", [("0.5", "quantity"), ("1.3", "quantity")])
def test_meter_quantity_rules(client, buyer, address, make_listing, auth_header, qty, field):
    listing, *_ = make_listing(min_quantity=Decimal(1), quantity_increment=Decimal("0.5"))
    r = _checkout(client, buyer, listing, address, qty, auth_header)
    assert r.status_code == 422 and r.json()["error"]["field"] == field


def test_piece_listing_rejects_fractions(client, buyer, address, make_listing, auth_header):
    listing, *_ = make_listing(unit="piece", stock=((None, 3),))
    assert _checkout(client, buyer, listing, address, "1.5", auth_header).status_code == 422


def test_insufficient_continuous_stock(client, buyer, address, make_listing, auth_header):
    # 3 m in total but no single 3 m cut
    listing, *_ = make_listing(stock=((Decimal("1.5"), 2),))
    r = _checkout(client, buyer, listing, address, "3", auth_header)
    assert r.status_code == 409 and r.json()["error"]["code"] == "insufficient_stock"


def test_cannot_buy_own_listing_or_draft(client, make_listing, address, buyer, auth_header):
    listing, merchant_user, _ = make_listing()
    own = client.post(f"{API}/addresses", headers=auth_header(merchant_user), json=ADDRESS).json()["data"]
    assert _checkout(client, merchant_user, listing, own, "1", auth_header).status_code == 422
    draft, *_ = make_listing(status="draft")
    assert _checkout(client, buyer, draft, address, "1", auth_header).status_code == 404


def test_addresses_are_private(client, make_user, address, make_listing, auth_header):
    listing, *_ = make_listing()
    other = make_user("other@example.com")
    assert _checkout(client, other, listing, address, "1", auth_header).status_code == 404
    assert client.get(f"{API}/addresses", headers=auth_header(other)).json()["data"] == []


# ---------- reservation + payment ----------

def test_full_purchase_flow_consumes_stock_and_keeps_remainder(client, session, buyer, address, make_listing, auth_header):
    listing, *_ = make_listing()
    co = _checkout(client, buyer, listing, address, "1.5", auth_header).json()["data"]
    conf = _confirm(client, buyer, co, auth_header)
    assert conf.status_code == 200
    data = conf.json()["data"]
    assert data["status"] == "payment_pending" and data["payment"]["status"] == "pending"
    assert _units(session, listing) == [(Decimal("3.00"), 0)]  # whole unit held during payment
    paid = _pay(client, buyer, data["payment"]["id"], auth_header).json()["data"]
    assert paid["payment"]["status"] == "succeeded"
    order = paid["order"]
    assert order["status"] == "confirmed" and order["total_idr"] == 185_000
    assert order["snapshot"]["simulated"] is True and order["events"][0]["simulated"] is True
    units = [u for u in _units(session, listing) if u[1] > 0]
    assert units == [(Decimal("1.50"), 1)]  # remainder returned to stock
    assert order["shipments"][0]["leg"] == "merchant_to_buyer"


def test_price_change_between_review_and_confirm_is_rejected(client, session, buyer, address, make_listing, auth_header):
    listing, *_ = make_listing()
    co = _checkout(client, buyer, listing, address, "1", auth_header).json()["data"]
    listing.price_idr = 120_000
    session.flush()
    r = _confirm(client, buyer, co, auth_header)
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_revision"
    assert _units(session, listing) == [(Decimal("3.00"), 1)]  # nothing was held


def test_wrong_expected_total_is_rejected(client, buyer, address, make_listing, auth_header):
    listing, *_ = make_listing()
    co = _checkout(client, buyer, listing, address, "1", auth_header).json()["data"]
    assert _confirm(client, buyer, co, auth_header, total=co["total_idr"] - 1).status_code == 409


def test_confirm_is_idempotent(client, session, buyer, address, make_listing, auth_header):
    listing, *_ = make_listing(stock=((Decimal(3), 2),))
    co = _checkout(client, buyer, listing, address, "1", auth_header).json()["data"]
    first = _confirm(client, buyer, co, auth_header, key="same")
    second = _confirm(client, buyer, co, auth_header, key="same")
    assert first.json() == second.json()
    held = session.scalar(select(func.count()).select_from(StockReservation))
    assert held == 1
    assert _units(session, listing) == [(Decimal("3.00"), 1)]  # held exactly one unit
    # the same key with a different request is a conflict
    other = client.post(f"{API}/fabric-checkouts/{co['id']}/confirm",
                        headers={**auth_header(buyer), "Idempotency-Key": "same"},
                        json={"expected_total_idr": 1})
    assert other.status_code == 409 and other.json()["error"]["code"] == "idempotency_conflict"


def test_confirm_requires_idempotency_key(client, buyer, address, make_listing, auth_header):
    listing, *_ = make_listing()
    co = _checkout(client, buyer, listing, address, "1", auth_header).json()["data"]
    r = client.post(f"{API}/fabric-checkouts/{co['id']}/confirm", headers=auth_header(buyer),
                    json={"expected_total_idr": co["total_idr"]})
    assert r.status_code == 422


def test_payment_is_idempotent_and_creates_one_order(client, session, buyer, address, make_listing, auth_header):
    from app.models import Order

    listing, *_ = make_listing()
    co = _checkout(client, buyer, listing, address, "1", auth_header).json()["data"]
    pid = _confirm(client, buyer, co, auth_header).json()["data"]["payment"]["id"]
    a = _pay(client, buyer, pid, auth_header, key="p1")
    b = _pay(client, buyer, pid, auth_header, key="p1")
    c = _pay(client, buyer, pid, auth_header, key="p2")  # new key, already succeeded
    assert a.json() == b.json()
    assert c.json()["data"]["order"]["id"] == a.json()["data"]["order"]["id"]
    assert session.scalar(select(func.count()).select_from(Order)) == 1


def test_failed_payment_releases_stock(client, session, buyer, address, make_listing, auth_header):
    listing, *_ = make_listing()
    co = _checkout(client, buyer, listing, address, "1", auth_header).json()["data"]
    pid = _confirm(client, buyer, co, auth_header).json()["data"]["payment"]["id"]
    out = _pay(client, buyer, pid, auth_header, outcome="failed").json()["data"]
    assert out["payment"]["status"] == "failed" and out["order"] is None
    assert _units(session, listing) == [(Decimal("3.00"), 1)]
    again = _pay(client, buyer, pid, auth_header, key="other")
    assert again.status_code == 409 and again.json()["error"]["code"] == "invalid_transition"


def test_expired_hold_is_released_and_payment_rejected(client, session, buyer, address, make_listing, auth_header):
    listing, *_ = make_listing()
    co = _checkout(client, buyer, listing, address, "1", auth_header).json()["data"]
    pid = _confirm(client, buyer, co, auth_header).json()["data"]["payment"]["id"]
    reservation = session.scalar(select(StockReservation))
    reservation.expires_at = reservation.expires_at - timedelta(hours=1)
    session.flush()
    r = _pay(client, buyer, pid, auth_header)
    assert r.status_code == 409 and r.json()["error"]["code"] == "payment_expired"
    assert _units(session, listing) == [(Decimal("3.00"), 1)]
    assert session.get(DemoPayment, uuid.UUID(pid)).status == "expired"


def test_expire_holds_sweeper(client, session, buyer, address, make_listing, auth_header):
    listing, *_ = make_listing()
    co = _checkout(client, buyer, listing, address, "1", auth_header).json()["data"]
    _confirm(client, buyer, co, auth_header)
    assert expire_holds(session) == 0  # still within the window
    session.scalar(select(StockReservation)).expires_at -= timedelta(hours=1)
    session.flush()
    assert expire_holds(session) == 1
    assert _units(session, listing) == [(Decimal("3.00"), 1)]


def test_best_fit_takes_shortest_sufficient_piece(client, session, buyer, address, make_listing, auth_header):
    listing, *_ = make_listing(stock=((Decimal(5), 1), (Decimal(2), 1)))
    co = _checkout(client, buyer, listing, address, "1.5", auth_header).json()["data"]
    _confirm(client, buyer, co, auth_header)
    assert _units(session, listing) == [(Decimal("2.00"), 0), (Decimal("5.00"), 1)]


def test_piece_purchase_decrements_pieces(client, session, buyer, address, make_listing, auth_header):
    listing, *_ = make_listing(unit="piece", stock=((None, 3),), price=250_000)
    order = _buy(client, buyer, listing, address, auth_header, qty="2")
    assert order["snapshot"]["subtotal_idr"] == 500_000
    assert _units(session, listing) == [(None, 1)]
    r = _checkout(client, buyer, listing, address, "2", auth_header)
    assert r.status_code == 409


def test_two_buyers_cannot_oversell_the_last_unit(engine):
    """Real concurrent transactions: the second reservation must not see the locked unit."""
    from sqlalchemy import delete
    from sqlalchemy.orm import sessionmaker

    from app.core.errors import InsufficientStock
    from app.models import (
        AuditEvent,
        DeliveryAddress,
        FabricCheckout,
        GalleryEntry,
        MerchantProfile,
        User,
    )
    from app.services import commerce as svc

    Factory = sessionmaker(engine, expire_on_commit=False)
    tag = uuid.uuid4().hex[:8]
    with Factory() as setup:
        users = [User(email=f"{n}-{tag}@example.com", password_hash="x", display_name=n)
                 for n in ("m", "a", "b")]
        setup.add_all(users)
        setup.flush()
        merchant = MerchantProfile(user_id=users[0].id, shop_name="T", city="Bandung",
                                   province="Jawa Barat")
        entry = GalleryEntry(slug=f"e-{tag}", name="E", status="published")
        setup.add_all([merchant, entry])
        setup.flush()
        listing = FabricListing(merchant_id=merchant.id, entry_id=entry.id, title="L",
                                selling_unit="meter", price_idr=1000, city="Bandung",
                                province="Jawa Barat", status="published")
        setup.add(listing)
        setup.flush()
        setup.add(FabricStockUnit(listing_id=listing.id, length_m=Decimal(2), quantity=1))
        for u in users[1:]:
            setup.add(DeliveryAddress(user_id=u.id, label="x", recipient_name="x", phone="123",
                                      line1="x", city="Jakarta", province="DKI Jakarta"))
        setup.flush()
        checkouts = []
        for u in users[1:]:
            addr = setup.scalar(select(DeliveryAddress).where(DeliveryAddress.user_id == u.id))
            checkouts.append(svc.create_checkout(setup, u, listing.id, Decimal(2), addr.id))
        setup.commit()
        ids = {"listing": listing.id, "entry": entry.id,
               "users": [u.id for u in users], "checkouts": [c.id for c in checkouts]}
    s1, s2 = Factory(), Factory()
    try:
        u1, u2 = s1.get(User, ids["users"][1]), s2.get(User, ids["users"][2])
        c1, c2 = s1.get(FabricCheckout, ids["checkouts"][0]), s2.get(FabricCheckout, ids["checkouts"][1])
        svc.confirm_checkout(s1, u1, c1, c1.total_idr)  # holds the only unit, uncommitted
        with pytest.raises(InsufficientStock):
            svc.confirm_checkout(s2, u2, c2, c2.total_idr)
        s1.commit()
        s2.rollback()
        with Factory() as check:
            assert check.scalar(select(func.count()).select_from(StockReservation).where(
                StockReservation.listing_id == ids["listing"])) == 1
    finally:
        s1.rollback()
        s2.rollback()
        s1.close()
        s2.close()
        with Factory() as cleanup:
            cleanup.execute(delete(StockReservation).where(StockReservation.listing_id == ids["listing"]))
            cleanup.execute(delete(FabricCheckout).where(FabricCheckout.listing_id == ids["listing"]))
            cleanup.execute(delete(AuditEvent).where(
                AuditEvent.target_id.in_([str(c) for c in ids["checkouts"]])))
            cleanup.execute(delete(User).where(User.id.in_(ids["users"])))
            cleanup.execute(delete(GalleryEntry).where(GalleryEntry.id == ids["entry"]))
            cleanup.commit()


# ---------- order lifecycle ----------

def _event(client, user, order_id, event, auth_header, note=None):
    return client.post(f"{API}/orders/{order_id}/events", headers=auth_header(user),
                       json={"event": event, "note": note})


def test_fabric_order_lifecycle_with_role_checks(client, buyer, address, make_listing, admin, auth_header):
    listing, merchant, _ = make_listing()
    order = _buy(client, buyer, listing, address, auth_header)
    oid = order["id"]
    assert _event(client, buyer, oid, "start_preparing", auth_header).status_code == 403
    assert _event(client, merchant, oid, "dispatch", auth_header).status_code == 409  # not prepared yet
    assert _event(client, merchant, oid, "start_preparing", auth_header).json()["data"]["status"] == "preparing"
    shipped = _event(client, merchant, oid, "dispatch", auth_header).json()["data"]
    assert shipped["status"] == "shipped_to_buyer"
    shipment = shipped["shipments"][0]
    assert shipment["tracking_no"].startswith("DEMO-") and shipment["simulated"] is True
    assert _event(client, buyer, oid, "confirm_receipt", auth_header).status_code == 409  # not delivered
    assert _event(client, merchant, oid, "simulate_delivery", auth_header).status_code == 403
    assert _event(client, admin, oid, "simulate_delivery", auth_header).json()["data"]["status"] == "delivered"
    done = _event(client, buyer, oid, "confirm_receipt", auth_header).json()["data"]
    assert done["status"] == "completed"
    assert [e["type"] for e in done["events"]] == [
        "order_confirmed", "start_preparing", "dispatch", "simulate_delivery", "confirm_receipt"]
    assert any(e["simulated"] for e in done["events"])
    assert _event(client, buyer, oid, "nonsense", auth_header).status_code == 422


def test_cancel_before_dispatch_restores_stock_and_reverses_settlement(client, session, buyer, address, make_listing, auth_header):
    listing, merchant, _ = make_listing()
    order = _buy(client, buyer, listing, address, auth_header, qty="1.5")
    oid = order["id"]
    assert _event(client, merchant, oid, "cancel", auth_header).status_code == 422  # reason required
    out = _event(client, merchant, oid, "cancel", auth_header, note="Stok rusak").json()["data"]
    assert out["status"] == "cancelled" and out["payment"]["status"] == "refund_recorded"
    lengths = sorted(u[0] for u in _units(session, listing) if u[1] > 0)
    assert lengths == [Decimal("1.50"), Decimal("1.50")]  # remainder + restored cut
    entries = client.get(f"{API}/orders/{oid}/settlement", headers=auth_header(merchant)).json()["data"]["entries"]
    assert [e["kind"] for e in entries] == ["sale", "adjustment"]
    assert sum(e["net_idr"] for e in entries) == 0


def test_cannot_cancel_after_dispatch(client, buyer, address, make_listing, auth_header):
    listing, merchant, _ = make_listing()
    oid = _buy(client, buyer, listing, address, auth_header)["id"]
    _event(client, merchant, oid, "start_preparing", auth_header)
    _event(client, merchant, oid, "dispatch", auth_header)
    r = _event(client, merchant, oid, "cancel", auth_header, note="terlambat")
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_transition"


def test_order_visibility(client, make_user, buyer, address, make_listing, admin, auth_header, make_partner):
    listing, merchant, _ = make_listing()
    oid = _buy(client, buyer, listing, address, auth_header)["id"]
    stranger = make_user("stranger@example.com")
    other_merchant, _ = make_partner("merchant", shop="Toko Lain")
    for who in (stranger, other_merchant):
        assert client.get(f"{API}/orders/{oid}", headers=auth_header(who)).status_code == 404
        assert _event(client, who, oid, "start_preparing", auth_header).status_code == 404
    for who in (buyer, merchant, admin):
        assert client.get(f"{API}/orders/{oid}", headers=auth_header(who)).status_code == 200


def test_order_lists_by_role(client, make_user, buyer, address, make_listing, admin, auth_header):
    listing, merchant, _ = make_listing(stock=((Decimal(3), 2),))
    _buy(client, buyer, listing, address, auth_header)
    assert len(client.get(f"{API}/orders", headers=auth_header(buyer)).json()["data"]["items"]) == 1
    mine = client.get(f"{API}/orders?as=merchant", headers=auth_header(merchant)).json()["data"]["items"]
    assert len(mine) == 1 and mine[0]["title"] == "Kain uji"
    assert client.get(f"{API}/orders?as=merchant", headers=auth_header(buyer)).status_code == 403
    assert client.get(f"{API}/orders?as=admin", headers=auth_header(buyer)).status_code == 403
    assert len(client.get(f"{API}/orders?as=admin", headers=auth_header(admin)).json()["data"]["items"]) == 1
    assert client.get(f"{API}/orders", headers=auth_header(make_user("n@example.com"))).json()["data"]["items"] == []


def test_settlement_views_and_no_double_charge(client, buyer, address, make_listing, admin, auth_header):
    listing, merchant, _ = make_listing()
    oid = _buy(client, buyer, listing, address, auth_header, qty="1.5")["id"]
    b = client.get(f"{API}/orders/{oid}/settlement", headers=auth_header(buyer)).json()["data"]
    assert b["buyer_total"]["total_idr"] == 185_000 and "entries" not in b
    m = client.get(f"{API}/orders/{oid}/settlement", headers=auth_header(merchant)).json()["data"]
    e = m["entries"][0]
    assert (e["gross_idr"], e["commission_bps"], e["commission_idr"], e["net_idr"]) == (
        150_000, 500, 7_500, 142_500)
    assert "buyer_total" not in m
    a = client.get(f"{API}/orders/{oid}/settlement", headers=auth_header(admin)).json()["data"]
    assert len(a["entries"]) == 1


def test_admin_sets_commission_rule_used_by_new_orders(client, buyer, address, make_listing, admin, auth_header):
    ah = auth_header(admin)
    r = client.post(f"{API}/admin/commission-rules", headers=ah,
                    json={"applies_to": "merchant_fabric", "rate_bps": 1000})
    assert r.status_code == 201
    assert client.post(f"{API}/admin/commission-rules", headers=ah,
                       json={"applies_to": "merchant_fabric", "rate_bps": 9999}).status_code == 422
    listing, merchant, _ = make_listing()
    oid = _buy(client, buyer, listing, address, auth_header, qty="1.5")["id"]
    e = client.get(f"{API}/orders/{oid}/settlement", headers=auth_header(merchant)).json()["data"]["entries"][0]
    assert e["commission_bps"] == 1000 and e["commission_idr"] == 15_000
    rules = client.get(f"{API}/admin/commission-rules", headers=ah).json()["data"]
    assert sum(1 for x in rules if x["active"]) == 1
    assert client.post(f"{API}/admin/commission-rules", headers=auth_header(buyer),
                       json={"applies_to": "merchant_fabric", "rate_bps": 1}).status_code == 403


def test_paid_order_keeps_snapshot_price_after_listing_changes(client, session, buyer, address, make_listing, auth_header):
    listing, *_ = make_listing()
    oid = _buy(client, buyer, listing, address, auth_header, qty="1")["id"]
    listing.price_idr = 999_999
    session.flush()
    order = client.get(f"{API}/orders/{oid}", headers=auth_header(buyer)).json()["data"]
    assert order["snapshot"]["unit_price_idr"] == 100_000 and order["total_idr"] == 135_000
