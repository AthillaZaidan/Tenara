import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import FabricListing, FabricStockUnit, MeasurementValue
from app.services import jobs
from app.services import templates as templates_svc
from app.services.prompt_interpreter import InterpretationFailed, LLMInterpreter

API = "/api/v1"
DIMS = {"chest_circumference": 96, "shoulder_width": 42, "back_length": 70, "sleeve_length": 22}


@pytest.fixture(autouse=True)
def synced(session):
    templates_svc.sync_templates(session)


@pytest.fixture
def entry(published_entry):
    return published_entry()


@pytest.fixture
def make_listing(session, make_partner, entry):
    def _make(unit="meter", width=110, material="katun", stock=((Decimal(3), 1),), **extra):
        _user, profile = make_partner("merchant", shop=f"Toko {uuid.uuid4().hex[:6]}")
        listing = FabricListing(
            merchant_id=profile.id, entry_id=entry.id, title="Kain kustom", selling_unit=unit,
            price_idr=200_000, material=material, city="Bandung", province="Jawa Barat",
            status="published", min_quantity=Decimal(1),
            quantity_increment=Decimal("0.5") if unit == "meter" else Decimal(1),
            usable_width_cm=width if unit == "meter" else None,
            piece_width_cm=width if unit == "piece" else None,
            piece_length_cm=200 if unit == "piece" else None, **extra)
        session.add(listing)
        session.flush()
        for length, qty in stock:
            session.add(FabricStockUnit(listing_id=listing.id,
                                        length_m=None if unit == "piece" else length, quantity=qty))
        session.flush()
        return listing

    return _make


@pytest.fixture
def buyer(make_user):
    return make_user("buyer@example.com")


@pytest.fixture
def h(buyer, auth_header):
    return auth_header(buyer)


def _create(client, h, listing, code="T01"):
    r = client.post(f"{API}/customizations", headers=h,
                    json={"listing_id": str(listing.id), "template_code": code})
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _prompt(client, h, cust_id, text, rev=1):
    r = client.post(f"{API}/customizations/{cust_id}/prompt-changes", headers=h,
                    json={"expected_design_revision": rev, "prompt": text})
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _apply(client, h, cust_id, rev, **body):
    return client.post(f"{API}/customizations/{cust_id}/revisions", headers=h,
                       json={"expected_design_revision": rev, **body})


# ---------- templates ----------

def test_sync_is_idempotent_and_versions_changes(session, monkeypatch):
    again = templates_svc.sync_templates(session)
    assert all(not row["created"] and row["version"] == 1 for row in again)
    from app.services import template_defs

    monkeypatch.setitem(template_defs.DEFINITIONS["T01"]["options"], "hem_length_delta_cm",
                        {"type": "number", "min": -4, "max": 4, "unit": "cm", "default": 0})
    changed = {r["code"]: r for r in templates_svc.sync_templates(session)}
    assert changed["T01"]["created"] and changed["T01"]["version"] == 2
    assert not changed["T02"]["created"]


def test_template_endpoints(client):
    items = client.get(f"{API}/garment-templates").json()["data"]
    assert [t["code"] for t in items] == ["T01", "T02", "T03", "T04", "T05"]
    one = client.get(f"{API}/garment-templates/t05").json()["data"]
    assert "trim" in one["options"] and "hip_circumference" in one["required_dimensions"]
    assert client.get(f"{API}/garment-templates/T09").status_code == 404


def test_admin_sync_requires_admin(client, buyer, auth_header, make_user):
    assert client.post(f"{API}/admin/garment-templates/sync", headers=auth_header(buyer)).status_code == 403
    admin = make_user("admin@example.com", roles=(("admin", "active"),))
    assert client.post(f"{API}/admin/garment-templates/sync", headers=auth_header(admin)).status_code == 200


def test_compatibility_explains_why(client, make_listing):
    narrow = make_listing(width=95)
    rows = {r["code"]: r for r in client.get(f"{API}/listings/{narrow.id}/templates").json()["data"]}
    assert rows["T01"]["compatible"] is True
    assert rows["T04"]["compatible"] is False and "minimal 100" in rows["T04"]["reasons"][0]
    missing = make_listing(material=None)
    assert all(not r["compatible"] for r in client.get(f"{API}/listings/{missing.id}/templates").json()["data"])


def test_create_requires_login_and_compatible_template(client, h, make_listing):
    listing = make_listing(width=95)
    assert client.post(f"{API}/customizations", json={"listing_id": str(listing.id), "template_code": "T01"}).status_code == 401
    r = client.post(f"{API}/customizations", headers=h,
                    json={"listing_id": str(listing.id), "template_code": "T04"})
    assert r.status_code == 422 and r.json()["error"]["field"] == "template_code"
    cust = _create(client, h, listing, "T01")
    assert cust["current_revision"] == 1 and cust["state"]["collar"] == "classic"
    assert cust["ready_for_tailor_validation"] is False


# ---------- prompt interpretation ----------

def test_prd_example_prompt_english(client, h, make_listing):
    cust = _create(client, h, make_listing())
    p = _prompt(client, h, cust["id"],
                "Add one left chest pocket, use wooden buttons, and shorten the hem by 3 cm.")
    got = {c["field"]: c["value"] for c in p["changes"]}
    assert got == {"pockets": "left_chest_single", "buttons": "wood_option_01",
                   "hem_length_delta_cm": -3}
    assert all(c["operation"] == "set" and c["status"] == "accepted" for c in p["changes"])
    assert p["requires_buyer_confirmation"] and p["requires_tailor_validation"]
    assert p["unsupported_requests"] == [] and p["clarifications"] == []
    assert "body_measurement" not in str(p)  # a hem cut is never a body-measurement change


def test_indonesian_prompt(client, h, make_listing):
    cust = _create(client, h, make_listing())
    p = _prompt(client, h, cust["id"], "Tambah saku dada kiri, kancing kayu, pendekkan 3 cm bagian bawah")
    got = {c["field"]: c["value"] for c in p["changes"]}
    assert got == {"pockets": "left_chest_single", "buttons": "wood_option_01",
                   "hem_length_delta_cm": -3}


def test_confirming_creates_new_revision_and_keeps_old(client, h, make_listing):
    cust = _create(client, h, make_listing())
    p = _prompt(client, h, cust["id"], "kancing kayu, pendekkan hem 3 cm")
    r = _apply(client, h, cust["id"], 1, proposal_id=p["proposal_id"])
    assert r.status_code == 201
    rev2 = r.json()["data"]
    assert rev2["revision"] == 2 and rev2["source"] == "prompt"
    assert rev2["state"]["buttons"] == "wood_option_01" and rev2["state"]["hem_length_delta_cm"] == -3
    first = client.get(f"{API}/customizations/{cust['id']}/revisions/1", headers=h).json()["data"]
    assert first["state"]["buttons"] == "plain_01"  # revision 1 is untouched
    assert client.get(f"{API}/customizations/{cust['id']}", headers=h).json()["data"]["current_revision"] == 2


def test_relative_lengths_accumulate(client, h, make_listing):
    cust = _create(client, h, make_listing())
    p1 = _prompt(client, h, cust["id"], "pendekkan hem 3 cm")
    _apply(client, h, cust["id"], 1, proposal_id=p1["proposal_id"])
    p2 = _prompt(client, h, cust["id"], "pendekkan hem 2 cm", rev=2)
    assert p2["changes"][0]["value"] == -5 and p2["changes"][0]["from"] == -3


@pytest.mark.parametrize("text", ["ubah jadi gaun", "kancing emas", "kerah bulu", "lengan panjang",
                                  "tambahkan bordir naga"])
def test_unsupported_requests_are_explained_not_accepted(client, h, make_listing, text):
    cust = _create(client, h, make_listing())
    p = _prompt(client, h, cust["id"], text)
    assert p["changes"] == []
    assert p["unsupported_requests"] and p["unsupported_requests"][0]["reason"]
    assert p["fallback"] == "structured_controls" and p["unapproved_note"] == text
    r = _apply(client, h, cust["id"], 1, proposal_id=p["proposal_id"])
    assert r.status_code == 422  # nothing to apply: unsupported text never becomes scope


def test_unsupported_button_offers_alternatives(client, h, make_listing):
    cust = _create(client, h, make_listing())
    p = _prompt(client, h, cust["id"], "pakai kancing emas")
    assert set(p["unsupported_requests"][0]["alternatives"]) == {"plain_01", "wood_option_01", "shell_option_01"}


def test_out_of_bounds_length_is_unsupported(client, h, make_listing):
    cust = _create(client, h, make_listing())
    p = _prompt(client, h, cust["id"], "pendekkan hem 50 cm")
    assert p["changes"] == [] and "antara -10 dan 10" in p["unsupported_requests"][0]["reason"]


def test_option_missing_on_template_is_unsupported(client, h, make_listing):
    cust = _create(client, h, make_listing(), "T03")  # vest has no sleeves
    p = _prompt(client, h, cust["id"], "pendekkan lengan 2 cm")
    assert p["changes"] == [] and "sleeve_length_delta_cm" in p["unsupported_requests"][0]["reason"]


def test_ambiguity_must_be_resolved_before_it_is_applied(client, h, make_listing):
    cust = _create(client, h, make_listing())
    p = _prompt(client, h, cust["id"], "tambah saku")
    clar = p["clarifications"][0]
    assert clar["field"] == "pockets" and "none" not in clar["choices"] and clar["id"] == "c0"
    assert _apply(client, h, cust["id"], 1, proposal_id=p["proposal_id"]).status_code == 422
    bad = _apply(client, h, cust["id"], 1, proposal_id=p["proposal_id"], resolutions={"c0": "giant_pocket"})
    assert bad.status_code == 422
    ok = _apply(client, h, cust["id"], 1, proposal_id=p["proposal_id"],
                resolutions={"c0": "left_chest_single"})
    assert ok.status_code == 201 and ok.json()["data"]["state"]["pockets"] == "left_chest_single"


def test_unresolved_clarification_stays_open_and_blocks_readiness(client, h, make_listing):
    cust = _create(client, h, make_listing())
    p = _prompt(client, h, cust["id"], "kancing kayu, tambah saku")
    rev = _apply(client, h, cust["id"], 1, proposal_id=p["proposal_id"]).json()["data"]
    assert rev["state"]["buttons"] == "wood_option_01" and rev["state"]["pockets"] == "none"
    assert [c["field"] for c in rev["open_clarifications"]] == ["pockets"]
    assert client.get(f"{API}/customizations/{cust['id']}", headers=h).json()["data"]["open_clarifications"]


def test_length_clarification_when_target_is_unclear(client, h, make_listing):
    cust = _create(client, h, make_listing())
    p = _prompt(client, h, cust["id"], "pendekkan 2 cm")
    clar = p["clarifications"][0]
    assert clar["field"] == "length" and set(clar["choices"]) == {"hem_length_delta_cm", "sleeve_length_delta_cm"}
    r = _apply(client, h, cust["id"], 1, proposal_id=p["proposal_id"],
               resolutions={clar["id"]: "sleeve_length_delta_cm"})
    assert r.json()["data"]["state"]["sleeve_length_delta_cm"] == -2


def test_conflicting_requests_become_a_clarification(client, h, make_listing):
    cust = _create(client, h, make_listing())
    p = _prompt(client, h, cust["id"], "saku dada kiri, saku dua di dada")
    assert p["changes"] == [] and p["clarifications"][0]["field"] == "pockets"
    assert set(p["clarifications"][0]["choices"]) == {"left_chest_single", "double_chest"}


def test_unrecognised_text_falls_back_to_structured_controls(client, h, make_listing):
    cust = _create(client, h, make_listing())
    p = _prompt(client, h, cust["id"], "xyzzy plugh")
    assert p["fallback"] == "structured_controls" and p["unapproved_note"] == "xyzzy plugh"


def test_trim_requires_compatible_material(client, h, make_listing):
    ok_cust = _create(client, h, make_listing(material="katun tenun"), "T05")
    assert _prompt(client, h, ok_cust["id"], "tambah rumbai panjang")["changes"][0]["value"] == "fringe_long"
    bad_cust = _create(client, h, make_listing(material="poliester"), "T05")
    p = _prompt(client, h, bad_cust["id"], "tambah rumbai panjang")
    assert p["changes"] == [] and "material" in p["unsupported_requests"][0]["reason"]


# ---------- stale / manual / revert ----------

def test_stale_expected_revision_is_rejected(client, h, make_listing):
    cust = _create(client, h, make_listing())
    r = client.post(f"{API}/customizations/{cust['id']}/prompt-changes", headers=h,
                    json={"expected_design_revision": 7, "prompt": "kancing kayu"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_revision"


def test_proposal_is_stale_after_design_moves_on(client, h, make_listing):
    cust = _create(client, h, make_listing())
    old = _prompt(client, h, cust["id"], "kancing kayu")
    _apply(client, h, cust["id"], 1, changes={"collar": "mandarin"})
    r = _apply(client, h, cust["id"], 2, proposal_id=old["proposal_id"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_revision"


def test_proposal_cannot_be_applied_twice(client, h, make_listing):
    cust = _create(client, h, make_listing())
    p = _prompt(client, h, cust["id"], "kancing kayu")
    assert _apply(client, h, cust["id"], 1, proposal_id=p["proposal_id"]).status_code == 201
    again = _apply(client, h, cust["id"], 2, proposal_id=p["proposal_id"])
    assert again.status_code == 422


def test_new_proposal_supersedes_the_previous_one(client, h, make_listing):
    cust = _create(client, h, make_listing())
    first = _prompt(client, h, cust["id"], "kancing kayu")
    _prompt(client, h, cust["id"], "kancing kerang")
    assert _apply(client, h, cust["id"], 1, proposal_id=first["proposal_id"]).status_code == 422


def test_manual_structured_controls(client, h, make_listing):
    cust = _create(client, h, make_listing())
    ok = _apply(client, h, cust["id"], 1, changes={"collar": "mandarin", "hem_length_delta_cm": 2})
    assert ok.status_code == 201 and ok.json()["data"]["source"] == "manual"
    assert _apply(client, h, cust["id"], 2, changes={"collar": "hoodie"}).status_code == 422
    r = _apply(client, h, cust["id"], 2, changes={"nonexistent": 1})
    assert r.status_code == 422
    assert _apply(client, h, cust["id"], 2, changes={"collar": "mandarin"}).status_code == 422  # no-op


def test_apply_needs_exactly_one_mode(client, h, make_listing):
    cust = _create(client, h, make_listing())
    assert _apply(client, h, cust["id"], 1).status_code == 422
    assert _apply(client, h, cust["id"], 1, changes={"collar": "none"}, revert_to_revision=1).status_code == 422


def test_revert_creates_traceable_revision(client, h, make_listing):
    cust = _create(client, h, make_listing())
    _apply(client, h, cust["id"], 1, changes={"collar": "mandarin"})
    _apply(client, h, cust["id"], 2, changes={"pockets": "double_chest"})
    r = _apply(client, h, cust["id"], 3, revert_to_revision=1)
    rev = r.json()["data"]
    assert rev["revision"] == 4 and rev["source"] == "revert" and rev["reverted_from"] == 1
    assert rev["state"]["collar"] == "classic" and rev["state"]["pockets"] == "none"
    assert _apply(client, h, cust["id"], 4, revert_to_revision=4).status_code == 422
    assert _apply(client, h, cust["id"], 4, revert_to_revision=99).status_code == 404
    revs = client.get(f"{API}/customizations/{cust['id']}/revisions", headers=h).json()["data"]
    assert [r["revision"] for r in revs] == [4, 3, 2, 1]


def test_customizations_are_private(client, make_user, auth_header, h, make_listing):
    cust = _create(client, h, make_listing())
    other = auth_header(make_user("other@example.com"))
    assert client.get(f"{API}/customizations/{cust['id']}", headers=other).status_code == 404
    assert _prompt_status(client, other, cust["id"]) == 404
    assert client.get(f"{API}/customizations", headers=other).json()["data"]["items"] == []


def _prompt_status(client, headers, cust_id):
    return client.post(f"{API}/customizations/{cust_id}/prompt-changes", headers=headers,
                       json={"expected_design_revision": 1, "prompt": "x"}).status_code


# ---------- LLM interpreter ----------

def test_llm_output_is_still_validated_by_the_server(client, h, make_listing, monkeypatch):
    cust = _create(client, h, make_listing())
    fake = LLMInterpreter(lambda msgs: '{"changes":[{"field":"pockets","value":"giant"},'
                                       '{"field":"collar","value":"mandarin"}]}')
    monkeypatch.setattr("app.services.customization.get_interpreters", lambda: [fake])
    p = _prompt(client, h, cust["id"], "terserah")
    assert p["interpreter"] == "llm"
    assert [c["field"] for c in p["changes"]] == ["collar"]
    assert p["unsupported_requests"][0]["text"] == "pockets=giant"


def test_llm_failure_falls_back_to_rules(client, h, make_listing, monkeypatch):
    def boom(msgs):
        raise OSError("network down")

    cust = _create(client, h, make_listing())
    monkeypatch.setattr("app.services.customization.get_interpreters",
                        lambda: [LLMInterpreter(boom), __import__(
                            "app.services.prompt_interpreter", fromlist=["x"]).RuleBasedInterpreter()])
    p = _prompt(client, h, cust["id"], "kancing kayu")
    assert p["interpreter"] == "rules" and p["changes"][0]["value"] == "wood_option_01"
    with pytest.raises(InterpretationFailed):
        LLMInterpreter(lambda m: "not json").interpret("x", {"options": {}}, {})


# ---------- previews ----------

def test_preview_is_bound_to_revision_and_goes_stale(client, session, h, make_listing):
    cust = _create(client, h, make_listing())
    r = client.post(f"{API}/customizations/{cust['id']}/product-previews", headers=h)
    assert r.status_code == 202
    preview = r.json()["data"]
    assert preview["status"] == "queued" and preview["design_revision"] == 1
    assert "konseptual" in preview["label"]
    _apply(client, h, cust["id"], 1, changes={"collar": "mandarin"})
    again = client.get(f"{API}/previews/{preview['id']}", headers=h).json()["data"]
    assert again["status"] == "stale"
    from app.models import Job

    job = session.scalar(select(Job).where(Job.kind == "preview.product"))
    assert job.subject_revision == 1 and job.subject_type == "customization"
    assert jobs.RESOLVERS["customization"](session, job.subject_id) == 2  # result would be superseded


def test_previews_are_private(client, make_user, auth_header, h, make_listing):
    cust = _create(client, h, make_listing())
    pid = client.post(f"{API}/customizations/{cust['id']}/product-previews", headers=h).json()["data"]["id"]
    assert client.get(f"{API}/previews/{pid}", headers=auth_header(make_user("o@example.com"))).status_code == 404


# ---------- measurements ----------

def _mset(client, h, values=None, height=170):
    r = client.post(f"{API}/measurement-sets", headers=h,
                    json={"height_cm": height, "values": values if values is not None else DIMS})
    assert r.status_code == 201, r.text
    return r.json()["data"]


def test_measurement_validation(client, h):
    assert client.post(f"{API}/measurement-sets", headers=h,
                       json={"height_cm": 170, "values": {"wrist": 15}}).status_code == 422
    assert client.post(f"{API}/measurement-sets", headers=h,
                       json={"height_cm": 170, "values": {"chest_circumference": 400}}).status_code == 422
    assert client.post(f"{API}/measurement-sets", headers=h, json={"height_cm": 20, "values": {}}).status_code == 422


def test_measurement_set_stores_manual_values_with_history(client, h):
    mset = _mset(client, h)
    chest = next(v for v in mset["values"] if v["key"] == "chest_circumference")
    assert chest["value_cm"] == 96.0 and chest["source"] == "manual" and len(chest["history"]) == 1
    assert "titik awal" in mset["notice"]


def test_correcting_an_estimate_keeps_the_original(client, session, h, buyer):
    mset = _mset(client, h, values={})
    from app.models import MeasurementValue as MV

    session.add(MV(set_id=mset["id"], key="shoulder_width", value_cm=Decimal("41.0"),
                   source="estimated", quality_flag="review_required", model_version="demo-1"))
    session.flush()
    r = client.patch(f"{API}/measurement-sets/{mset['id']}", headers=h,
                     json={"expected_revision": 1, "values": {"shoulder_width": 43.5}})
    row = next(v for v in r.json()["data"]["values"] if v["key"] == "shoulder_width")
    assert row["value_cm"] == 43.5 and row["source"] == "corrected"
    assert row["original_value_cm"] == 41.0 and row["model_version"] == "demo-1"
    assert row["history"][-1]["from"] == "41.0" and row["history"][-1]["to"] == "43.5"
    stale = client.patch(f"{API}/measurement-sets/{mset['id']}", headers=h,
                         json={"expected_revision": 1, "values": {"shoulder_width": 44}})
    assert stale.status_code == 409


def test_clearing_a_value_marks_it_manual_required(client, h):
    mset = _mset(client, h)
    r = client.patch(f"{API}/measurement-sets/{mset['id']}", headers=h,
                     json={"expected_revision": 1, "values": {"sleeve_length": None}})
    row = next(v for v in r.json()["data"]["values"] if v["key"] == "sleeve_length")
    assert row["value_cm"] is None and row["source"] == "manual_required"


def test_confirm_needs_every_required_dimension(client, h, make_listing):
    cust = _create(client, h, make_listing())
    partial = _mset(client, h, values={"chest_circumference": 96})
    r = client.post(f"{API}/measurement-sets/{partial['id']}/confirm", headers=h,
                    json={"customization_id": cust["id"]})
    assert r.status_code == 422 and "sleeve_length" in r.json()["error"]["message"]
    full = _mset(client, h)
    ok = client.post(f"{API}/measurement-sets/{full['id']}/confirm", headers=h,
                     json={"customization_id": cust["id"]})
    assert ok.json()["data"]["status"] == "confirmed"
    edited = client.patch(f"{API}/measurement-sets/{full['id']}", headers=h,
                          json={"expected_revision": 1, "values": {"chest_circumference": 98}})
    assert edited.json()["data"]["status"] == "draft"  # edits need reconfirmation


def test_measurements_are_private(client, make_user, auth_header, h, make_listing):
    mset = _mset(client, h)
    other = auth_header(make_user("o@example.com"))
    assert client.get(f"{API}/measurement-sets/{mset['id']}", headers=other).status_code == 404
    cust = _create(client, auth_header(make_user("o2@example.com")), make_listing())
    r = client.post(f"{API}/customizations/{cust['id']}/measurement-set", headers=auth_header(make_user("o3@example.com")),
                    json={"measurement_set_id": mset["id"]})
    assert r.status_code == 404


# ---------- material estimate ----------

def _ready(client, h, listing, code="T01", dims=None):
    cust = _create(client, h, listing, code)
    mset = _mset(client, h, values=dims or DIMS)
    client.post(f"{API}/customizations/{cust['id']}/measurement-set", headers=h,
                json={"measurement_set_id": mset["id"]})
    return cust, mset


def _estimate(client, h, cust_id):
    return client.post(f"{API}/customizations/{cust_id}/material-estimates", headers=h)


def test_estimate_matches_hand_calculation(client, h, make_listing):
    cust, _ = _ready(client, h, make_listing())
    est = _estimate(client, h, cust["id"]).json()["data"]
    r = est["result"]
    # panel 59 cm: front+back do not fit side by side on 110 cm -> 2x74; sleeves 26; collar +10
    assert r["fits"] is True and r["required_length_cm"] == 184.0
    assert r["breakdown_cm"] == {"body": 148.0, "sleeves": 26.0, "options": 10.0}
    assert r["purchase_quantity"] == "2.00" and Decimal(r["surplus_m"]) == Decimal("0.16")
    assert r["tailor_validation_required"] is True and r["stock_ok"] is True
    assert est["stale"] is False and any("demo" in a for a in r["assumptions"])


def test_estimate_reacts_to_design_options(client, h, make_listing):
    cust, _ = _ready(client, h, make_listing())
    _apply(client, h, cust["id"], 1, changes={"hem_length_delta_cm": -3, "pockets": "left_chest_single"})
    r = _estimate(client, h, cust["id"]).json()["data"]["result"]
    # body 2x71 = 142, sleeves 26, collar 10 + pocket 12
    assert r["required_length_cm"] == 190.0


def test_estimate_rounds_up_to_pattern_repeat(client, h, make_listing):
    cust, _ = _ready(client, h, make_listing(pattern_repeat_cm=30))
    assert _estimate(client, h, cust["id"]).json()["data"]["result"]["required_length_cm"] == 210.0


def test_narrow_fabric_does_not_fit(client, h, make_listing):
    wide_body = {**DIMS, "chest_circumference": 190}  # panel 109 cm > 95 cm fabric
    cust, _ = _ready(client, h, make_listing(width=95), dims=wide_body)
    r = _estimate(client, h, cust["id"]).json()["data"]["result"]
    assert r["fits"] is False and "tidak cukup" in r["reason"] and r["stock_ok"] is False
    assert "purchase_quantity" not in r


def test_piece_listing_counts_whole_pieces(client, h, make_listing):
    cust, _ = _ready(client, h, make_listing(unit="piece", stock=((None, 4),)))
    r = _estimate(client, h, cust["id"]).json()["data"]["result"]
    assert r["purchase_quantity"] == "1" and r["surplus_cm"] == 16.0 and r["stock_ok"] is True


def test_estimate_reports_insufficient_continuous_stock(client, h, make_listing):
    cust, _ = _ready(client, h, make_listing(stock=((Decimal("1.5"), 3),)))
    assert _estimate(client, h, cust["id"]).json()["data"]["result"]["stock_ok"] is False


def test_estimate_requires_measurements(client, h, make_listing):
    cust = _create(client, h, make_listing())
    r = _estimate(client, h, cust["id"])
    assert r.status_code == 422 and r.json()["error"]["field"] == "measurements"
    mset = _mset(client, h, values={"chest_circumference": 96})
    client.post(f"{API}/customizations/{cust['id']}/measurement-set", headers=h,
                json={"measurement_set_id": mset["id"]})
    assert _estimate(client, h, cust["id"]).status_code == 422


def test_estimate_goes_stale_when_inputs_change(client, session, h, make_listing):
    listing = make_listing()
    cust, mset = _ready(client, h, listing)
    _estimate(client, h, cust["id"])
    cur = lambda: client.get(f"{API}/customizations/{cust['id']}/material-estimates/current", headers=h).json()["data"]
    assert cur()["stale"] is False
    _apply(client, h, cust["id"], 1, changes={"collar": "mandarin"})
    assert cur()["stale_reasons"] == ["design_revision_changed"]
    _estimate(client, h, cust["id"])
    assert cur()["stale"] is False
    client.patch(f"{API}/measurement-sets/{mset['id']}", headers=h,
                 json={"expected_revision": 1, "values": {"chest_circumference": 100}})
    assert "measurements_changed" in cur()["stale_reasons"]
    _estimate(client, h, cust["id"])
    listing.revision += 1
    session.flush()
    assert cur()["stale_reasons"] == ["listing_changed"]


def test_only_the_latest_estimate_is_current(client, session, h, make_listing):
    cust, _ = _ready(client, h, make_listing())
    _estimate(client, h, cust["id"])
    _estimate(client, h, cust["id"])
    from app.models import MaterialEstimate

    statuses = sorted(e.status for e in session.scalars(select(MaterialEstimate)))
    assert statuses == ["current", "superseded"]


def test_readiness_needs_confirmed_measurements_and_fresh_estimate(client, h, make_listing):
    cust, mset = _ready(client, h, make_listing())
    detail = lambda: client.get(f"{API}/customizations/{cust['id']}", headers=h).json()["data"]
    assert detail()["ready_for_tailor_validation"] is False
    _estimate(client, h, cust["id"])
    assert detail()["ready_for_tailor_validation"] is False  # measurements not confirmed yet
    client.post(f"{API}/measurement-sets/{mset['id']}/confirm", headers=h,
                json={"customization_id": cust["id"]})
    assert detail()["ready_for_tailor_validation"] is True  # confirmed + current estimate
    _apply(client, h, cust["id"], 1, changes={"collar": "none"})
    assert detail()["ready_for_tailor_validation"] is False  # design moved on: estimate is stale


def test_measurement_value_rows_are_unique_per_key(session, client, h):
    _mset(client, h)
    keys = [r.key for r in session.scalars(select(MeasurementValue))]
    assert len(keys) == len(set(keys))
