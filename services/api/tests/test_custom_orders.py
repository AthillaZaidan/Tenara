import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import (
    FabricListing,
    FabricStockUnit,
    Order,
    Quote,
    SettlementEntry,
    StockReservation,
    TailorCapability,
)
from app.models.custom import CustomRequest
from app.services import templates as templates_svc

API = "/api/v1"
DIMS = {"chest_circumference": 96, "shoulder_width": 42, "back_length": 70, "sleeve_length": 22}
ADDRESS = {"label": "Rumah", "recipient_name": "Budi", "phone": "0812345", "line1": "Jl. Mawar 1",
           "city": "Jakarta", "province": "DKI Jakarta"}


@pytest.fixture(autouse=True)
def synced(session):
    templates_svc.sync_templates(session)


class Scene:
    """Everything a custom order needs, built through the public API where it matters."""


@pytest.fixture
def scene(client, session, make_user, make_partner, published_entry, auth_header):
    s = Scene()
    s.client, s.session, s.auth = client, session, auth_header
    s.entry = published_entry()
    s.merchant, s.merchant_profile = make_partner("merchant", shop=f"Toko {uuid.uuid4().hex[:5]}",
                                                  city="Bandung", province="Jawa Barat")
    s.tailor, s.tailor_profile = make_partner("tailor", shop=f"Jahit {uuid.uuid4().hex[:5]}",
                                              city="Bandung", province="Jawa Barat")
    session.add(TailorCapability(tailor_id=s.tailor_profile.id, template_code="T01",
                                 base_rate_idr=300_000, lead_time_days=14, weekly_capacity=3,
                                 materials=["katun"], supported_options={}))
    s.listing = FabricListing(
        merchant_id=s.merchant_profile.id, entry_id=s.entry.id, title="Kain tenun", price_idr=200_000,
        selling_unit="meter", material="katun", usable_width_cm=110, city="Bandung",
        province="Jawa Barat", status="published", min_quantity=Decimal(1),
        quantity_increment=Decimal("0.5"))
    session.add(s.listing)
    session.flush()
    session.add(FabricStockUnit(listing_id=s.listing.id, length_m=Decimal(3), quantity=1))
    session.flush()
    s.buyer = make_user("buyer@example.com")
    s.admin = make_user("admin@example.com", roles=(("admin", "active"),))
    s.h = {"buyer": auth_header(s.buyer), "merchant": auth_header(s.merchant),
           "tailor": auth_header(s.tailor), "admin": auth_header(s.admin)}
    s.address = client.post(f"{API}/addresses", headers=s.h["buyer"], json=ADDRESS).json()["data"]
    return s


def _ready_customization(s, **state_changes):
    c = s.client
    cust = c.post(f"{API}/customizations", headers=s.h["buyer"],
                  json={"listing_id": str(s.listing.id), "template_code": "T01"}).json()["data"]
    if state_changes:
        c.post(f"{API}/customizations/{cust['id']}/revisions", headers=s.h["buyer"],
               json={"expected_design_revision": 1, "changes": state_changes})
    mset = c.post(f"{API}/measurement-sets", headers=s.h["buyer"],
                  json={"height_cm": 170, "values": DIMS}).json()["data"]
    c.post(f"{API}/customizations/{cust['id']}/measurement-set", headers=s.h["buyer"],
           json={"measurement_set_id": mset["id"]})
    c.post(f"{API}/measurement-sets/{mset['id']}/confirm", headers=s.h["buyer"],
           json={"customization_id": cust["id"]})
    est = c.post(f"{API}/customizations/{cust['id']}/material-estimates", headers=s.h["buyer"])
    assert est.status_code == 201, est.text
    s.cust, s.mset = cust, mset
    return cust


def _request(s, tailor_profile=None):
    r = s.client.post(f"{API}/custom-requests", headers=s.h["buyer"], json={
        "customization_id": s.cust["id"],
        "tailor_id": str((tailor_profile or s.tailor_profile).id),
        "delivery_address_id": s.address["id"]})
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _submit(s, req_id):
    r = s.client.post(f"{API}/custom-requests/{req_id}/submit", headers=s.h["buyer"])
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _confirm(s, req_id, decision="confirm", reason=None):
    return s.client.post(f"{API}/custom-requests/{req_id}/merchant-confirmation",
                         headers=s.h["merchant"], json={"decision": decision, "reason": reason})


SPEC = {"fabric_purchase_quantity": "2.0", "finished_dimensions": {"chest_width": 55.0, "length": 72.0},
        "lead_time_days": 14, "extra_materials": [{"name": "Kancing kayu 6 pcs", "provider": "tailor",
                                                   "price_idr": 25_000}],
        "surcharges": [{"description": "Saku dada kiri", "amount_idr": 20_000}]}


def _spec(s, req_id, **override):
    return s.client.post(f"{API}/custom-requests/{req_id}/production-spec", headers=s.h["tailor"],
                         json={**SPEC, **override})


def _quote(s, req_id, spec_id, hours=48):
    r = s.client.post(f"{API}/custom-requests/{req_id}/quotes", headers=s.h["tailor"],
                      json={"spec_id": spec_id, "expires_in_hours": hours})
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _to_quote(s, **state_changes):
    _ready_customization(s, **state_changes)
    req = _request(s)
    _submit(s, req["id"])
    assert _confirm(s, req["id"]).status_code == 200
    spec = _spec(s, req["id"]).json()["data"]
    return req, _quote(s, req["id"], spec["id"])


def _accept(s, quote, key="accept-1", **override):
    body = {"expected_quote_revision": quote["revision"], "acknowledged_visual_reference": True,
            "delivery_address_id": s.address["id"], **override}
    return s.client.post(f"{API}/quotes/{quote['id']}/accept",
                         headers={**s.h["buyer"], "Idempotency-Key": key}, json=body)


def _pay(s, payment_id, outcome="succeeded", key="pay-1"):
    return s.client.post(f"{API}/demo-payments/{payment_id}/complete",
                         headers={**s.h["buyer"], "Idempotency-Key": key}, json={"outcome": outcome})


def _order(s):
    _req_unused, quote = _to_quote(s)
    payment = _accept(s, quote).json()["data"]["payment"]
    return _pay(s, payment["id"]).json()["data"]["order"]


def _event(s, who, order_id, event, note=None):
    return s.client.post(f"{API}/orders/{order_id}/events", headers=s.h[who],
                         json={"event": event, "note": note})


# ---------- matching ----------

def test_recommendations_are_explained_and_exclude_ineligible(scene, make_partner):
    s = scene
    _ready_customization(s)
    _other, other_profile = make_partner("tailor", shop="Jahit Jauh", city="Medan", province="Sumatera Utara")
    s.session.add(TailorCapability(tailor_id=other_profile.id, template_code="T01",
                                   base_rate_idr=250_000, lead_time_days=7, materials=["katun"]))
    nocap, _ = make_partner("tailor", shop="Tanpa Kapabilitas")
    url = (f"{API}/tailors/recommendations?customization_id={s.cust['id']}"
           f"&delivery_address_id={s.address['id']}")
    items = s.client.get(url, headers=s.h["buyer"]).json()["data"]["items"]
    assert [i["shop_name"] for i in items] == [s.tailor_profile.shop_name, "Jahit Jauh"] or \
        {i["shop_name"] for i in items} == {s.tailor_profile.shop_name, "Jahit Jauh"}
    first = next(i for i in items if i["tailor_id"] == str(s.tailor_profile.id))
    assert any("Lead time 14 hari" in r for r in first["reasons"])
    assert all(i["shop_name"] != "Tanpa Kapabilitas" for i in items)
    assert nocap is not None


def test_service_area_and_declared_options_filter_tailors(scene, make_partner):
    s = scene
    cap = s.session.scalar(select(TailorCapability))
    cap.supported_options = {"pockets": ["left_chest_single"]}
    area_user, area_profile = make_partner("tailor", shop="Area Sempit")
    area_profile.service_area = ["Jawa Timur"]
    s.session.add(TailorCapability(tailor_id=area_profile.id, template_code="T01",
                                   base_rate_idr=200_000, lead_time_days=5))
    s.session.flush()
    _ready_customization(s, pockets="double_chest")  # not in this tailor's declared options
    url = (f"{API}/tailors/recommendations?customization_id={s.cust['id']}"
           f"&delivery_address_id={s.address['id']}")
    names = [i["shop_name"] for i in s.client.get(url, headers=s.h["buyer"]).json()["data"]["items"]]
    assert s.tailor_profile.shop_name not in names and "Area Sempit" not in names
    assert area_user is not None


def test_recommendations_are_private(scene, make_user, auth_header):
    s = scene
    _ready_customization(s)
    other = make_user("other@example.com")
    r = s.client.get(f"{API}/tailors/recommendations?customization_id={s.cust['id']}"
                     f"&delivery_address_id={s.address['id']}", headers=auth_header(other))
    assert r.status_code == 404


# ---------- request lifecycle ----------

def test_request_needs_a_ready_design(scene):
    s = scene
    cust = s.client.post(f"{API}/customizations", headers=s.h["buyer"],
                         json={"listing_id": str(s.listing.id), "template_code": "T01"}).json()["data"]
    s.cust = cust
    r = s.client.post(f"{API}/custom-requests", headers=s.h["buyer"], json={
        "customization_id": cust["id"], "tailor_id": str(s.tailor_profile.id),
        "delivery_address_id": s.address["id"]})
    assert r.status_code == 422 and r.json()["error"]["field"] == "measurements"


def test_ineligible_tailor_cannot_be_selected(scene, make_partner):
    s = scene
    _ready_customization(s)
    _, nocap = make_partner("tailor", shop="Tanpa Kapabilitas")
    r = s.client.post(f"{API}/custom-requests", headers=s.h["buyer"], json={
        "customization_id": s.cust["id"], "tailor_id": str(nocap.id),
        "delivery_address_id": s.address["id"]})
    assert r.status_code == 422 and r.json()["error"]["field"] == "tailor_id"


def test_one_open_request_per_design(scene):
    s = scene
    _ready_customization(s)
    _request(s)
    r = s.client.post(f"{API}/custom-requests", headers=s.h["buyer"], json={
        "customization_id": s.cust["id"], "tailor_id": str(s.tailor_profile.id),
        "delivery_address_id": s.address["id"]})
    assert r.status_code == 422


def test_submit_snapshots_design_measurements_and_estimate(scene):
    s = scene
    _ready_customization(s, collar="mandarin")
    req = _request(s)
    assert req["status"] == "draft" and req["revision"] == 0
    sub = _submit(s, req["id"])
    assert sub["status"] == "submitted" and sub["revision"] == 1
    assert sub["design_state"]["collar"] == "mandarin"
    assert sub["measurements_cm"]["chest_circumference"] == 96.0
    assert sub["estimate"]["purchase_quantity"] == "2.00"


def test_partners_see_only_what_they_need(scene, make_partner):
    s = scene
    _ready_customization(s)
    req = _request(s)
    _submit(s, req["id"])
    m = s.client.get(f"{API}/custom-requests/{req['id']}", headers=s.h["merchant"]).json()["data"]
    assert "measurements_cm" not in m and "address" not in m and "design_state" not in m
    assert m["requested_quantity"] == "2.00"
    t = s.client.get(f"{API}/custom-requests/{req['id']}", headers=s.h["tailor"]).json()["data"]
    assert t["measurements_cm"] and t["design_state"] and t["address"]["city"] == "Jakarta"
    stranger, _ = make_partner("merchant", shop="Toko Asing")
    assert s.client.get(f"{API}/custom-requests/{req['id']}", headers=s.auth(stranger)).status_code == 404


def test_tailor_gets_the_product_preview_but_never_the_on_body_try_on(scene, storage):
    from app.main import app
    from app.models import Customization, Preview
    from app.services.files import create_file
    from app.services.storage import get_storage

    s = scene
    app.dependency_overrides[get_storage] = lambda: storage
    _ready_customization(s)
    cust = s.session.get(Customization, s.cust["id"])

    def preview(kind, revision, data):
        f = create_file(s.session, storage, owner_id=s.buyer.id, kind="preview", data=data,
                        content_type="image/png")
        s.session.add(Preview(customization_id=cust.id, design_revision=revision, kind=kind,
                              status="completed", file_id=f.id))
        s.session.flush()
        return f

    product = preview("product", cust.current_revision, b"\x89PNG product")
    preview("on_body", cust.current_revision, b"\x89PNG try-on on the buyer's photo")
    req = _request(s)
    _submit(s, req["id"])
    t = s.client.get(f"{API}/custom-requests/{req['id']}", headers=s.h["tailor"]).json()["data"]
    assert str(product.id) in t["design_preview"]["url"] and "konseptual" in t["design_preview"]["label"]
    image = s.client.get(t["design_preview"]["url"])  # the signed link works for the tailor
    assert image.status_code == 200 and image.content == b"\x89PNG product"
    m = s.client.get(f"{API}/custom-requests/{req['id']}", headers=s.h["merchant"]).json()["data"]
    assert "design_preview" not in m


def test_without_a_current_product_preview_the_tailor_gets_data_only(scene, storage):
    from app.models import Customization, Preview
    from app.services.files import create_file

    s = scene
    _ready_customization(s, collar="mandarin")  # design is now at revision 2
    cust = s.session.get(Customization, s.cust["id"])
    old = create_file(s.session, storage, owner_id=s.buyer.id, kind="preview", data=b"\x89PNG old",
                      content_type="image/png")
    s.session.add(Preview(customization_id=cust.id, design_revision=cust.current_revision - 1,
                          kind="product", status="completed", file_id=old.id))
    s.session.flush()
    req = _request(s)
    _submit(s, req["id"])
    t = s.client.get(f"{API}/custom-requests/{req['id']}", headers=s.h["tailor"]).json()["data"]
    assert t["design_preview"] is None and t["measurements_cm"]


def test_merchant_confirmation_checks_stock_and_records_price(scene):
    s = scene
    _ready_customization(s)
    req = _request(s)
    _submit(s, req["id"])
    r = _confirm(s, req["id"])
    assert r.status_code == 200 and r.json()["data"]["status"] == "validating"
    s.session.expire_all()
    assert s.session.scalar(select(CustomRequest)).status == "validating"


def test_merchant_rejection_returns_request_for_revision(scene):
    s = scene
    _ready_customization(s)
    req = _request(s)
    _submit(s, req["id"])
    assert _confirm(s, req["id"], "reject").status_code == 422
    r = _confirm(s, req["id"], "reject", "Stok sudah terjual")
    assert r.json()["data"]["status"] == "needs_revision"
    assert "Stok sudah terjual" in r.json()["data"]["reject_reason"]
    again = _submit(s, req["id"])
    assert again["revision"] == 2 and again["status"] == "submitted"


def test_merchant_cannot_confirm_without_stock(scene):
    s = scene
    _ready_customization(s)
    req = _request(s)
    _submit(s, req["id"])
    unit = s.session.scalar(select(FabricStockUnit))
    unit.quantity = 0
    s.session.flush()
    r = _confirm(s, req["id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "insufficient_stock"


def test_only_the_assigned_merchant_can_confirm(scene, make_partner):
    s = scene
    _ready_customization(s)
    req = _request(s)
    _submit(s, req["id"])
    other, _ = make_partner("merchant", shop="Toko Lain")
    r = s.client.post(f"{API}/custom-requests/{req['id']}/merchant-confirmation",
                      headers=s.auth(other), json={"decision": "confirm"})
    assert r.status_code == 404


def test_tailor_can_return_or_reject(scene):
    s = scene
    _ready_customization(s)
    req = _request(s)
    _submit(s, req["id"])
    r = s.client.post(f"{API}/custom-requests/{req['id']}/tailor-decision", headers=s.h["tailor"],
                      json={"action": "return_for_revision", "reason": "Ukuran dada perlu dicek"})
    assert r.json()["data"]["status"] == "needs_revision"
    _submit(s, req["id"])
    r = s.client.post(f"{API}/custom-requests/{req['id']}/tailor-decision", headers=s.h["tailor"],
                      json={"action": "reject", "reason": "Kapasitas penuh"})
    assert r.json()["data"]["status"] == "rejected"


# ---------- spec + quote ----------

def test_spec_requires_merchant_confirmation_and_valid_quantity(scene):
    s = scene
    _ready_customization(s)
    req = _request(s)
    _submit(s, req["id"])
    no_conf = _spec(s, req["id"])
    assert no_conf.status_code == 422 and no_conf.json()["error"]["field"] == "merchant_confirmation"
    _confirm(s, req["id"])
    too_much = _spec(s, req["id"], fabric_purchase_quantity="2.5")
    assert too_much.status_code == 422 and too_much.json()["error"]["field"] == "fabric_purchase_quantity"
    bad_inc = _spec(s, req["id"], fabric_purchase_quantity="1.3")
    assert bad_inc.status_code == 422
    empty = _spec(s, req["id"], finished_dimensions={})
    assert empty.status_code == 422
    ok = _spec(s, req["id"])
    body = ok.json()["data"]
    assert ok.status_code == 201 and body["specification"]["fabric"]["surplus_handling"] == "returned_with_garment"
    assert "dikirim kembali" in body["specification"]["fabric"]["surplus_note"]


def test_tailor_may_use_less_fabric_than_requested(scene):
    s = scene
    _ready_customization(s)
    req = _request(s)
    _submit(s, req["id"])
    _confirm(s, req["id"])
    spec = _spec(s, req["id"], fabric_purchase_quantity="1.5").json()["data"]
    assert spec["specification"]["change_from_request"]["fabric_quantity_changed"] is True
    quote = _quote(s, req["id"], spec["id"])
    fabric = next(line for line in quote["lines"] if line["kind"] == "fabric")
    assert fabric["amount_idr"] == 300_000  # 1.5 m x 200.000


def test_quote_is_itemised_with_owners_and_two_shipping_legs(scene):
    s = scene
    _, quote = _to_quote(s)
    lines = {ln["kind"]: ln for ln in quote["lines"]}
    assert lines["fabric"]["amount_idr"] == 400_000 and lines["fabric"]["owner"] == "merchant"
    assert lines["tailoring_base"]["amount_idr"] == 300_000
    assert lines["surcharge"]["amount_idr"] == 20_000
    assert lines["extra_material"]["owner"] == "tailor"
    assert lines["shipping_leg_1"]["amount_idr"] == 10_000  # Bandung -> Bandung (simulated)
    assert lines["shipping_leg_2"]["amount_idr"] == 35_000  # Bandung -> Jakarta (simulated)
    assert quote["total_idr"] == 400_000 + 300_000 + 20_000 + 25_000 + 10_000 + 35_000
    assert quote["status"] == "issued" and quote["acceptable"] is True
    assert quote["changes_from_request"]["fabric_quantity_in_quote"] == "2.0"
    assert "SIMULASI" in quote["simulation_notice"] and quote["surplus_fabric"]


def test_new_quote_supersedes_previous_and_old_one_cannot_be_accepted(scene):
    s = scene
    req, first = _to_quote(s)
    spec2 = _spec(s, req["id"], lead_time_days=10).json()["data"]
    second = _quote(s, req["id"], spec2["id"])
    assert second["revision"] == first["revision"] + 1
    old = s.client.get(f"{API}/quotes/{first['id']}", headers=s.h["buyer"]).json()["data"]
    assert old["status"] == "superseded"
    r = _accept(s, first)
    assert r.status_code == 409


def test_merchant_cannot_see_quotes(scene):
    s = scene
    _, quote = _to_quote(s)
    assert s.client.get(f"{API}/quotes/{quote['id']}", headers=s.h["merchant"]).status_code == 403


def test_switching_tailor_voids_the_quote(scene, make_partner):
    s = scene
    req, quote = _to_quote(s)
    s.client.post(f"{API}/custom-requests/{req['id']}/tailor-decision", headers=s.h["tailor"],
                  json={"action": "return_for_revision", "reason": "Perlu revisi"})
    other, other_profile = make_partner("tailor", shop="Penjahit Baru", city="Bandung",
                                        province="Jawa Barat")
    s.session.add(TailorCapability(tailor_id=other_profile.id, template_code="T01",
                                   base_rate_idr=250_000, lead_time_days=7, materials=["katun"]))
    s.session.flush()
    r = s.client.patch(f"{API}/custom-requests/{req['id']}", headers=s.h["buyer"],
                       json={"tailor_id": str(other_profile.id)})
    assert r.status_code == 200 and r.json()["data"]["tailor_id"] == str(other_profile.id)
    s.session.expire_all()
    assert s.session.get(Quote, uuid.UUID(quote["id"])).status == "superseded"
    assert other is not None


def test_request_cannot_be_edited_while_awaiting_the_buyer(scene):
    s = scene
    req, _ = _to_quote(s)
    r = s.client.patch(f"{API}/custom-requests/{req['id']}", headers=s.h["buyer"],
                       json={"delivery_address_id": s.address["id"]})
    assert r.status_code == 409


# ---------- accept + pay ----------

def test_accept_needs_idempotency_key_and_acknowledgement(scene):
    s = scene
    _, quote = _to_quote(s)
    no_key = s.client.post(f"{API}/quotes/{quote['id']}/accept", headers=s.h["buyer"], json={
        "expected_quote_revision": 1, "acknowledged_visual_reference": True,
        "delivery_address_id": s.address["id"]})
    assert no_key.status_code == 422
    r = _accept(s, quote, acknowledged_visual_reference=False)
    assert r.status_code == 422 and r.json()["error"]["field"] == "acknowledged_visual_reference"
    assert _accept(s, quote, key="k2", delivery_address_id=str(uuid.uuid4())).status_code == 422
    assert _accept(s, quote, key="k3", expected_quote_revision=9).status_code == 409


def test_only_the_buyer_can_accept(scene):
    s = scene
    _, quote = _to_quote(s)
    r = s.client.post(f"{API}/quotes/{quote['id']}/accept",
                      headers={**s.h["tailor"], "Idempotency-Key": "x"},
                      json={"expected_quote_revision": 1, "acknowledged_visual_reference": True,
                            "delivery_address_id": s.address["id"]})
    assert r.status_code in (403, 404)


def test_accept_holds_stock_and_is_idempotent(scene):
    s = scene
    _, quote = _to_quote(s)
    first = _accept(s, quote, key="same")
    second = _accept(s, quote, key="same")
    assert first.status_code == 200 and first.json() == second.json()
    assert first.json()["data"]["payment"]["status"] == "pending"
    assert s.session.scalar(select(FabricStockUnit)).quantity == 0  # whole unit held
    assert len(list(s.session.scalars(select(StockReservation)))) == 1
    # a different key while a payment is pending reuses it instead of holding more stock
    third = _accept(s, quote, key="other")
    assert third.json()["data"]["payment"]["id"] == first.json()["data"]["payment"]["id"]


def test_payment_creates_a_custom_order_with_snapshot_and_two_legs(scene):
    s = scene
    req, quote = _to_quote(s, collar="mandarin")
    payment = _accept(s, quote).json()["data"]["payment"]
    paid = _pay(s, payment["id"]).json()["data"]
    order = paid["order"]
    assert order["kind"] == "custom" and order["status"] == "confirmed"
    assert order["total_idr"] == quote["total_idr"]
    snap = order["snapshot"]
    assert snap["visual_reference_acknowledged"] is True and snap["design_revision"] == 2
    assert snap["specification"]["design_state"]["collar"] == "mandarin"
    assert snap["measurements_cm"]["chest_circumference"] == 96.0
    assert len(snap["quote"]["lines"]) == len(quote["lines"])
    assert [sh["leg"] for sh in order["shipments"]] == ["merchant_to_tailor", "tailor_to_buyer"] or \
        {sh["leg"] for sh in order["shipments"]} == {"merchant_to_tailor", "tailor_to_buyer"}
    s.session.expire_all()
    assert s.session.get(CustomRequest, uuid.UUID(req["id"])).status == "converted_to_order"
    assert s.session.get(Quote, uuid.UUID(quote["id"])).status == "accepted"
    remainder = [u for u in s.session.scalars(select(FabricStockUnit)) if u.quantity > 0]
    assert [u.length_m for u in remainder] == [Decimal("1.00")]  # 3 m - 2 m returned to stock
    assert _accept(s, quote, key="late").status_code == 409  # already accepted


def test_settlement_splits_merchant_and_tailor_revenue(scene):
    s = scene
    order = _order(s)
    entries = {e.party_role: e for e in s.session.scalars(select(SettlementEntry))}
    assert (entries["merchant"].gross_idr, entries["merchant"].commission_idr,
            entries["merchant"].net_idr) == (400_000, 20_000, 380_000)
    # tailor: base 300.000 + surcharge 20.000 + own material 25.000 = 345.000; 5% = 17.250
    assert (entries["tailor"].gross_idr, entries["tailor"].commission_idr,
            entries["tailor"].net_idr) == (345_000, 17_250, 327_750)
    buyer = s.client.get(f"{API}/orders/{order['id']}/settlement", headers=s.h["buyer"]).json()["data"]
    assert buyer["buyer_total"]["total_idr"] == order["total_idr"] and "entries" not in buyer
    tailor = s.client.get(f"{API}/orders/{order['id']}/settlement", headers=s.h["tailor"]).json()["data"]
    assert [e["party_role"] for e in tailor["entries"]] == ["tailor"]


def test_failed_payment_releases_stock_and_allows_retry(scene):
    s = scene
    _req_unused, quote = _to_quote(s)
    payment = _accept(s, quote).json()["data"]["payment"]
    out = _pay(s, payment["id"], "failed").json()["data"]
    assert out["payment"]["status"] == "failed" and out["order"] is None
    assert s.session.scalar(select(FabricStockUnit)).quantity == 1
    retry = _accept(s, quote, key="retry")
    assert retry.status_code == 200 and retry.json()["data"]["payment"]["status"] == "pending"


def test_expired_hold_blocks_payment_and_frees_stock(scene):
    s = scene
    _, quote = _to_quote(s)
    payment = _accept(s, quote).json()["data"]["payment"]
    reservation = s.session.scalar(select(StockReservation))
    reservation.expires_at = reservation.expires_at - timedelta(hours=1)
    s.session.flush()
    r = _pay(s, payment["id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "payment_expired"
    assert s.session.scalar(select(FabricStockUnit)).quantity == 1


def test_expired_quote_cannot_be_accepted(scene):
    s = scene
    _, quote = _to_quote(s)
    s.session.get(Quote, uuid.UUID(quote["id"])).expires_at -= timedelta(days=30)
    s.session.flush()
    assert s.client.get(f"{API}/quotes/{quote['id']}", headers=s.h["buyer"]).json()["data"]["status"] == "expired"
    assert _accept(s, quote).status_code == 409


def test_quote_is_stale_when_the_design_changes(scene):
    s = scene
    _, quote = _to_quote(s)
    s.client.post(f"{API}/customizations/{s.cust['id']}/revisions", headers=s.h["buyer"],
                  json={"expected_design_revision": 1, "changes": {"collar": "none"}})
    view = s.client.get(f"{API}/quotes/{quote['id']}", headers=s.h["buyer"]).json()["data"]
    assert view["acceptable"] is False and "design_revision_changed" in view["stale_reasons"]
    r = _accept(s, quote)
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_revision"


def test_quote_is_stale_when_measurements_change(scene):
    s = scene
    _, quote = _to_quote(s)
    s.client.patch(f"{API}/measurement-sets/{s.mset['id']}", headers=s.h["buyer"],
                   json={"expected_revision": 1, "values": {"chest_circumference": 100}})
    assert _accept(s, quote).status_code == 409


def test_suspended_partner_blocks_acceptance(scene):
    s = scene
    _, quote = _to_quote(s)
    s.tailor_profile.status = "suspended"
    s.session.flush()
    assert _accept(s, quote).status_code == 422


# ---------- fulfilment ----------

def _through_inspection(s):
    order = _order(s)
    oid = order["id"]
    assert _event(s, "merchant", oid, "start_preparing").status_code == 200
    assert _event(s, "merchant", oid, "dispatch_to_tailor").status_code == 200
    assert _event(s, "tailor", oid, "receive_fabric").status_code == 200
    return oid


def _inspect(s, oid, passed=True, notes=None):
    return s.client.post(f"{API}/orders/{oid}/fabric-inspection", headers=s.h["tailor"], json={
        "passed": passed, "measured_width_cm": "110.0", "measured_length_m": "2.00",
        "condition": "baik" if passed else "bernoda", "notes": notes})


def test_full_custom_lifecycle_with_two_shipments(scene):
    s = scene
    oid = _through_inspection(s)
    order = s.client.get(f"{API}/orders/{oid}", headers=s.h["buyer"]).json()["data"]
    leg1 = next(sh for sh in order["shipments"] if sh["leg"] == "merchant_to_tailor")
    assert leg1["status"] == "delivered" and leg1["tracking_no"].startswith("DEMO-")
    assert _event(s, "tailor", oid, "begin_production").status_code == 409  # not inspected yet
    ins = _inspect(s, oid)
    assert ins.status_code == 201 and ins.json()["data"]["order_status"] == "inspection_passed"
    assert _event(s, "tailor", oid, "begin_production").json()["data"]["status"] == "in_production"
    assert _event(s, "tailor", oid, "complete_production").status_code == 422  # QC note required
    assert _event(s, "tailor", oid, "complete_production", "QC lulus").json()["data"]["status"] == "quality_check"
    assert _event(s, "merchant", oid, "dispatch_finished").status_code == 403
    shipped = _event(s, "tailor", oid, "dispatch_finished").json()["data"]
    assert shipped["status"] == "shipped_to_buyer"
    assert _event(s, "buyer", oid, "confirm_receipt").status_code == 409
    assert _event(s, "admin", oid, "simulate_delivery").json()["data"]["status"] == "delivered"
    done = _event(s, "buyer", oid, "confirm_receipt").json()["data"]
    assert done["status"] == "completed"
    legs = {sh["leg"]: sh["status"] for sh in done["shipments"]}
    assert legs == {"merchant_to_tailor": "delivered", "tailor_to_buyer": "delivered"}
    assert [e["type"] for e in done["events"]] == [
        "order_confirmed", "start_preparing", "dispatch_to_tailor", "receive_fabric",
        "fabric_inspection", "begin_production", "complete_production", "dispatch_finished",
        "simulate_delivery", "confirm_receipt"]


def test_wrong_roles_and_wrong_states_are_rejected(scene):
    s = scene
    oid = _order(s)["id"]
    assert _event(s, "tailor", oid, "start_preparing").status_code == 403
    assert _event(s, "buyer", oid, "dispatch_to_tailor").status_code == 403
    assert _event(s, "merchant", oid, "dispatch_to_tailor").status_code == 409  # not prepared yet
    assert _event(s, "tailor", oid, "receive_fabric").status_code == 409
    assert _event(s, "merchant", oid, "nonsense").status_code == 422


def test_failed_inspection_pauses_cutting_until_resolved(scene):
    s = scene
    oid = _through_inspection(s)
    assert _inspect(s, oid, passed=False).status_code == 422  # notes required
    r = _inspect(s, oid, passed=False, notes="Ada noda pada kain")
    assert r.json()["data"]["order_status"] == "inspection_issue"
    assert _event(s, "tailor", oid, "begin_production").status_code == 409
    assert _event(s, "admin", oid, "resolve_issue").status_code == 422
    assert _event(s, "admin", oid, "resolve_issue", "Disepakati lanjut").json()["data"]["status"] == "received_by_tailor"
    assert _inspect(s, oid).json()["data"]["order_status"] == "inspection_passed"
    assert _event(s, "merchant", oid, "fail_fulfillment", "x").status_code in (403, 409)


def test_failed_fulfilment_refunds_and_reverses_settlement(scene):
    s = scene
    oid = _through_inspection(s)
    _inspect(s, oid, passed=False, notes="Kain rusak")
    out = _event(s, "admin", oid, "fail_fulfillment", "Kain tidak layak").json()["data"]
    assert out["status"] == "failed_fulfillment" and out["payment"]["status"] == "refund_recorded"
    nets = [e.net_idr for e in s.session.scalars(select(SettlementEntry))]
    assert sum(nets) == 0
    stock = [u for u in s.session.scalars(select(FabricStockUnit)) if u.quantity > 0]
    assert [u.length_m for u in stock] == [Decimal("1.00")]  # cut fabric is not restored


def test_cancel_before_dispatch_restores_stock(scene):
    s = scene
    oid = _order(s)["id"]
    assert _event(s, "merchant", oid, "cancel").status_code == 422
    out = _event(s, "tailor", oid, "cancel", "Kapasitas penuh").json()["data"]
    assert out["status"] == "cancelled" and out["payment"]["status"] == "refund_recorded"
    lengths = sorted(u.length_m for u in s.session.scalars(select(FabricStockUnit)) if u.quantity > 0)
    assert lengths == [Decimal("1.00"), Decimal("2.00")]
    assert sum(e.net_idr for e in s.session.scalars(select(SettlementEntry))) == 0
    assert _event(s, "merchant", oid, "cancel", "lagi").status_code == 409


def test_cannot_cancel_once_fabric_shipped(scene):
    s = scene
    oid = _order(s)["id"]
    _event(s, "merchant", oid, "start_preparing")
    _event(s, "merchant", oid, "dispatch_to_tailor")
    assert _event(s, "merchant", oid, "cancel", "terlambat").status_code == 409


def test_merchant_never_sees_body_or_design_data_on_orders(scene):
    s = scene
    oid = _order(s)["id"]
    merchant = s.client.get(f"{API}/orders/{oid}", headers=s.h["merchant"]).json()["data"]["snapshot"]
    assert "measurements_cm" not in merchant and "address" not in merchant
    assert "design_state" not in merchant["specification"]
    assert "measurements_cm" not in merchant["specification"]
    tailor = s.client.get(f"{API}/orders/{oid}", headers=s.h["tailor"]).json()["data"]["snapshot"]
    assert tailor["measurements_cm"] and tailor["address"]["city"] == "Jakarta"
    assert s.client.get(f"{API}/orders/{oid}", headers=s.h["buyer"]).json()["data"]["snapshot"]["measurements_cm"]


def test_orders_can_be_listed_as_tailor(scene):
    s = scene
    _order(s)
    items = s.client.get(f"{API}/orders?as=tailor", headers=s.h["tailor"]).json()["data"]["items"]
    assert len(items) == 1
    assert s.client.get(f"{API}/orders?as=tailor", headers=s.h["buyer"]).status_code == 403
    assert len(s.client.get(f"{API}/custom-requests?as=tailor", headers=s.h["tailor"]).json()["data"]["items"]) == 1
    assert len(s.client.get(f"{API}/custom-requests?as=merchant", headers=s.h["merchant"]).json()["data"]["items"]) == 1


def test_approved_snapshot_is_never_edited_by_amendments(scene):
    s = scene
    order = _order(s)
    oid = order["id"]
    before = s.session.get(Order, uuid.UUID(oid)).snapshot
    r = s.client.post(f"{API}/orders/{oid}/amendments", headers=s.h["tailor"], json={
        "reason": "Pembeli minta saku tambahan", "changes": {"pockets": "double_chest"},
        "price_delta_idr": 20_000})
    assert r.status_code == 201
    aid = r.json()["data"]["id"]
    deny = s.client.post(f"{API}/orders/{oid}/amendments/{aid}/decision", headers=s.h["tailor"],
                         json={"decision": "approve"})
    assert deny.status_code == 403  # only the buyer decides
    ok = s.client.post(f"{API}/orders/{oid}/amendments/{aid}/decision", headers=s.h["buyer"],
                       json={"decision": "approve"})
    assert ok.json()["data"]["status"] == "approved"
    again = s.client.post(f"{API}/orders/{oid}/amendments/{aid}/decision", headers=s.h["buyer"],
                          json={"decision": "reject"})
    assert again.status_code == 409
    s.session.expire_all()
    assert s.session.get(Order, uuid.UUID(oid)).snapshot == before
    listed = s.client.get(f"{API}/orders/{oid}/amendments", headers=s.h["merchant"]).json()["data"]
    assert len(listed) == 1


def test_buyer_can_withdraw_before_ordering(scene):
    s = scene
    req, quote = _to_quote(s)
    r = s.client.post(f"{API}/custom-requests/{req['id']}/withdraw", headers=s.h["buyer"])
    assert r.json()["data"]["status"] == "withdrawn"
    assert _accept(s, quote).status_code in (409, 422)
