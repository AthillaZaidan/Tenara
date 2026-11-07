import uuid

import pytest
from sqlalchemy import select
from test_custom_orders import (  # noqa: F401  (fixtures + helpers shared with the order tests)
    _event,
    _inspect,
    _order,
    _through_inspection,
    scene,
    synced,
)

from app.main import app
from app.models import AuditEvent, SettlementEntry
from app.services.storage import get_storage

API = "/api/v1"


@pytest.fixture
def oid(scene):  # noqa: F811
    return _order(scene)["id"]


@pytest.fixture
def evidence(scene, make_file):  # noqa: F811
    return make_file(scene.buyer)


def _open_conv(s, who, order_id, with_role):
    return s.client.post(f"{API}/conversations", headers=s.h[who],
                         json={"order_id": order_id, "with": with_role})


def _claim(s, order_id, target="merchant", component="fabric", files=()):
    return s.client.post(f"{API}/orders/{order_id}/claims", headers=s.h["buyer"], json={
        "target": target, "component": component,
        "description": "Pola saku tidak sesuai dengan spesifikasi yang disetujui",
        "evidence_file_ids": [str(f.id) for f in files]})


def _respond(s, who, claim_id, kind, reason="Alasan", proposal=None):
    body = {"kind": kind, "reason": reason}
    if proposal:
        body["proposal"] = proposal
    return s.client.post(f"{API}/claims/{claim_id}/responses", headers=s.h[who], json=body)


def _reject(s, claim_id):
    r = _respond(s, "merchant", claim_id, "rejection", "Sesuai spesifikasi")
    assert r.status_code == 201, r.text
    return next(x for x in r.json()["data"]["responses"] if x["kind"] == "rejection")["id"]


def _appeal(s, claim_id, rejection_id):
    return s.client.post(f"{API}/claims/{claim_id}/appeals", headers=s.h["buyer"], json={
        "partner_rejection_id": rejection_id, "reason": "Saku tidak sesuai desain yang disetujui"})


def _decide(s, appeal_id, who="admin", **body):
    body = {"outcome": "overturned", "remedy_type": "refund_partial", "amount_idr": 100_000,
            "reasoning": "Bukti menunjukkan penempatan saku berbeda dari spesifikasi", **body}
    return s.client.post(f"{API}/appeals/{appeal_id}/decision", headers=s.h[who], json=body)


# ---------- chat ----------

def test_conversation_is_scoped_to_buyer_and_the_chosen_partner(scene, oid):  # noqa: F811
    s = scene
    r = _open_conv(s, "buyer", oid, "merchant")
    assert r.status_code == 201
    conv = r.json()["data"]
    assert {m["role"] for m in conv["members"]} == {"buyer", "merchant"}
    again = _open_conv(s, "merchant", oid, "merchant")
    assert again.json()["data"]["id"] == conv["id"]  # same thread, no duplicates
    tailor_thread = _open_conv(s, "buyer", oid, "tailor").json()["data"]
    assert tailor_thread["id"] != conv["id"]
    assert {m["role"] for m in tailor_thread["members"]} == {"buyer", "tailor"}


def test_other_partner_cannot_open_or_read_the_thread(scene, oid):  # noqa: F811
    s = scene
    assert _open_conv(s, "tailor", oid, "merchant").status_code == 403
    conv = _open_conv(s, "buyer", oid, "merchant").json()["data"]
    s.client.post(f"{API}/conversations/{conv['id']}/messages", headers=s.h["buyer"],
                  json={"body": "Apakah stok aman?"})
    assert s.client.get(f"{API}/conversations/{conv['id']}/messages", headers=s.h["tailor"]).status_code == 404
    assert s.client.post(f"{API}/conversations/{conv['id']}/messages", headers=s.h["tailor"],
                         json={"body": "intip"}).status_code == 404
    assert s.client.get(f"{API}/conversations/{conv['id']}/messages", headers=s.h["admin"]).status_code == 404


def test_strangers_cannot_open_conversations(scene, oid, make_user, auth_header):  # noqa: F811
    s = scene
    stranger = auth_header(make_user("stranger@example.com"))
    r = s.client.post(f"{API}/conversations", headers=stranger,
                      json={"order_id": oid, "with": "merchant"})
    assert r.status_code == 404


def test_messages_are_ordered_and_pollable(scene, oid):  # noqa: F811
    s = scene
    conv = _open_conv(s, "buyer", oid, "merchant").json()["data"]
    url = f"{API}/conversations/{conv['id']}/messages"
    for who, text in (("buyer", "Halo"), ("merchant", "Ya, stok aman"), ("buyer", "Terima kasih")):
        assert s.client.post(url, headers=s.h[who], json={"body": text}).status_code == 201
    page = s.client.get(url, headers=s.h["merchant"]).json()["data"]
    assert [m["body"] for m in page["items"]] == ["Halo", "Ya, stok aman", "Terima kasih"]
    s.client.post(url, headers=s.h["merchant"], json={"body": "Segera dikirim"})
    new = s.client.get(f"{url}?after={page['next_cursor']}", headers=s.h["buyer"]).json()["data"]
    assert [m["body"] for m in new["items"]] == ["Segera dikirim"]
    idle = s.client.get(f"{url}?after={new['next_cursor']}", headers=s.h["buyer"]).json()["data"]
    assert idle["items"] == [] and idle["next_cursor"] == new["next_cursor"]


def test_message_validation(scene, oid):  # noqa: F811
    s = scene
    conv = _open_conv(s, "buyer", oid, "merchant").json()["data"]
    url = f"{API}/conversations/{conv['id']}/messages"
    assert s.client.post(url, headers=s.h["buyer"], json={"body": ""}).status_code == 422
    assert s.client.post(url, headers=s.h["buyer"], json={"body": "x" * 2001}).status_code == 422
    assert s.client.post(url, headers=s.h["buyer"], json={"body": "   "}).status_code == 422
    assert s.client.get(f"{url}?after=bogus", headers=s.h["buyer"]).status_code == 422


def test_conversation_list_shows_only_mine(scene, oid, make_user, auth_header):  # noqa: F811
    s = scene
    conv = _open_conv(s, "buyer", oid, "merchant").json()["data"]
    s.client.post(f"{API}/conversations/{conv['id']}/messages", headers=s.h["buyer"], json={"body": "Hai"})
    mine = s.client.get(f"{API}/conversations", headers=s.h["merchant"]).json()["data"]
    assert [c["id"] for c in mine] == [conv["id"]] and mine[0]["last_message"]["body"] == "Hai"
    assert s.client.get(f"{API}/conversations", headers=s.h["tailor"]).json()["data"] == []
    other = auth_header(make_user("o@example.com"))
    assert s.client.get(f"{API}/conversations", headers=other).json()["data"] == []


def test_conversation_can_be_opened_before_ordering(scene):  # noqa: F811
    from test_custom_orders import _ready_customization, _request, _submit

    s = scene
    _ready_customization(s)
    req = _request(s)
    _submit(s, req["id"])
    r = s.client.post(f"{API}/conversations", headers=s.h["buyer"],
                      json={"request_id": req["id"], "with": "tailor"})
    assert r.status_code == 201 and r.json()["data"]["request_id"] == req["id"]
    assert s.client.post(f"{API}/conversations", headers=s.h["buyer"],
                         json={"request_id": req["id"], "order_id": str(uuid.uuid4()),
                               "with": "tailor"}).status_code == 422


# ---------- claims: opening + evidence ----------

def test_buyer_opens_claim_with_dedicated_discussion(scene, oid, evidence):  # noqa: F811
    s = scene
    r = _claim(s, oid, "merchant", "fabric", [evidence])
    assert r.status_code == 201
    claim = r.json()["data"]
    assert claim["status"] == "opened" and claim["target_role"] == "merchant"
    assert claim["evidence"][0]["url"].startswith("/api/v1/files/")
    conv = s.client.get(f"{API}/conversations/{claim['conversation_id']}/messages", headers=s.h["merchant"])
    assert conv.status_code == 200
    assert s.client.get(f"{API}/conversations/{claim['conversation_id']}/messages",
                        headers=s.h["tailor"]).status_code == 404  # other partner is not copied in
    assert _claim(s, oid, "merchant", "fabric").status_code == 422  # duplicate open claim
    assert _claim(s, oid, "tailor", "garment").status_code == 201


def test_only_the_buyer_opens_claims_and_evidence_must_be_own(scene, oid, make_file):  # noqa: F811
    s = scene
    r = s.client.post(f"{API}/orders/{oid}/claims", headers=s.h["merchant"],
                      json={"target": "merchant", "component": "fabric", "description": "tidak boleh"})
    assert r.status_code == 403
    foreign = make_file(s.merchant)
    assert _claim(s, oid, files=[foreign]).status_code == 422


def test_claims_are_private(scene, oid, make_user, auth_header):  # noqa: F811
    s = scene
    claim = _claim(s, oid).json()["data"]
    stranger = auth_header(make_user("stranger@example.com"))
    assert s.client.get(f"{API}/claims/{claim['id']}", headers=stranger).status_code == 404
    assert s.client.get(f"{API}/claims/{claim['id']}", headers=s.h["tailor"]).status_code == 404
    assert s.client.get(f"{API}/claims/{claim['id']}", headers=s.h["admin"]).status_code == 404
    assert s.client.get(f"{API}/claims", headers=stranger).json()["data"]["items"] == []
    assert len(s.client.get(f"{API}/claims", headers=s.h["merchant"]).json()["data"]["items"]) == 1


def test_evidence_urls_are_signed_for_participants(scene, oid, evidence, storage):  # noqa: F811
    s = scene
    app.dependency_overrides[get_storage] = lambda: storage
    claim = _claim(s, oid, files=[evidence]).json()["data"]
    url = s.client.get(f"{API}/claims/{claim['id']}", headers=s.h["merchant"]).json()["data"]["evidence"][0]["url"]
    assert s.client.get(url).status_code == 200
    assert s.client.get(url.split("?")[0]).status_code == 403  # no token, no access


def test_partner_can_add_their_own_evidence(scene, oid, make_file):  # noqa: F811
    s = scene
    claim = _claim(s, oid).json()["data"]
    mine = make_file(s.merchant)
    r = s.client.post(f"{API}/claims/{claim['id']}/evidence", headers=s.h["merchant"],
                      json={"file_id": str(mine.id), "note": "Foto sebelum dikirim"})
    assert r.status_code == 201
    other = make_file(s.buyer)
    assert s.client.post(f"{API}/claims/{claim['id']}/evidence", headers=s.h["merchant"],
                         json={"file_id": str(other.id)}).status_code == 422


# ---------- claims: partner response ----------

def test_proposal_needs_a_valid_remedy(scene, oid):  # noqa: F811
    s = scene
    claim = _claim(s, oid).json()["data"]
    assert _respond(s, "merchant", claim["id"], "proposal").status_code == 422
    assert _respond(s, "merchant", claim["id"], "proposal",
                    proposal={"remedy_type": "refund_partial"}).status_code == 422  # amount missing
    assert _respond(s, "buyer", claim["id"], "discussion").status_code == 403
    ok = _respond(s, "merchant", claim["id"], "discussion", "Kami cek dulu")
    assert ok.json()["data"]["status"] == "partner_discussion"


def test_accepting_a_proposal_resolves_without_touching_the_order(scene, oid):  # noqa: F811
    s = scene
    claim = _claim(s, oid).json()["data"]
    prop = _respond(s, "merchant", claim["id"], "proposal", "Kami beri refund sebagian",
                    {"remedy_type": "refund_partial", "amount_idr": 50_000}).json()["data"]
    assert prop["status"] == "resolution_proposed"
    rid = prop["responses"][-1]["id"]
    assert s.client.post(f"{API}/claims/{claim['id']}/proposals/{rid}/decision", headers=s.h["merchant"],
                         json={"decision": "accept"}).status_code == 403
    done = s.client.post(f"{API}/claims/{claim['id']}/proposals/{rid}/decision", headers=s.h["buyer"],
                         json={"decision": "accept"}).json()["data"]
    assert done["status"] == "resolved"
    order = s.client.get(f"{API}/orders/{oid}", headers=s.h["buyer"]).json()["data"]
    assert order["status"] == "confirmed"  # claim resolution is independent of the order status
    again = s.client.post(f"{API}/claims/{claim['id']}/proposals/{rid}/decision", headers=s.h["buyer"],
                          json={"decision": "accept"})
    assert again.status_code == 409


def test_accepted_refund_is_executed_separately_and_only_hits_the_responsible_party(scene, oid):  # noqa: F811
    s = scene
    claim = _claim(s, oid).json()["data"]
    _respond(s, "merchant", claim["id"], "proposal", "Refund sebagian",
             {"remedy_type": "refund_partial", "amount_idr": 100_000})
    rid = s.client.get(f"{API}/claims/{claim['id']}", headers=s.h["buyer"]).json()["data"]["responses"][-1]["id"]
    s.client.post(f"{API}/claims/{claim['id']}/proposals/{rid}/decision", headers=s.h["buyer"],
                  json={"decision": "accept"})
    assert s.client.post(f"{API}/claims/{claim['id']}/remedy-events", headers=s.h["buyer"],
                         json={"action": "refund_partial", "amount_idr": 100_000}).status_code == 403
    assert s.client.post(f"{API}/claims/{claim['id']}/remedy-events", headers=s.h["merchant"],
                         json={"action": "refund_full"}).status_code == 422  # not what was agreed
    assert s.client.post(f"{API}/claims/{claim['id']}/remedy-events", headers=s.h["merchant"],
                         json={"action": "refund_partial", "amount_idr": 200_000}).status_code == 422
    r = s.client.post(f"{API}/claims/{claim['id']}/remedy-events", headers=s.h["merchant"],
                      json={"action": "refund_partial", "amount_idr": 100_000})
    assert r.status_code == 201 and r.json()["data"]["simulated"] is True
    entries = list(s.session.scalars(select(SettlementEntry).where(SettlementEntry.kind == "adjustment")))
    assert len(entries) == 1 and entries[0].party_role == "merchant"
    assert (entries[0].gross_idr, entries[0].commission_idr, entries[0].net_idr) == (-100_000, -5_000, -95_000)
    detail = s.client.get(f"{API}/claims/{claim['id']}", headers=s.h["buyer"]).json()["data"]
    assert detail["remedy_events"][0]["simulated"] is True and "SIMULASI" in detail["simulation_notice"]


def test_refund_can_be_executed_in_instalments_but_never_beyond_the_order(scene, oid):  # noqa: F811
    s = scene
    claim = _claim(s, oid).json()["data"]
    _respond(s, "merchant", claim["id"], "proposal", "Refund",
             {"remedy_type": "refund_partial", "amount_idr": 100_000})
    rid = s.client.get(f"{API}/claims/{claim['id']}", headers=s.h["buyer"]).json()["data"]["responses"][-1]["id"]
    s.client.post(f"{API}/claims/{claim['id']}/proposals/{rid}/decision", headers=s.h["buyer"],
                  json={"decision": "accept"})
    url = f"{API}/claims/{claim['id']}/remedy-events"
    assert s.client.post(url, headers=s.h["merchant"], json={"action": "refund_partial", "amount_idr": 60_000}).status_code == 201
    assert s.client.post(url, headers=s.h["merchant"], json={"action": "refund_partial", "amount_idr": 60_000}).status_code == 422
    assert s.client.post(url, headers=s.h["merchant"], json={"action": "refund_partial", "amount_idr": 40_000}).status_code == 201
    assert s.client.post(url, headers=s.h["merchant"], json={"action": "refund_partial", "amount_idr": 1}).status_code == 409
    total = sum(e.net_idr for e in s.session.scalars(select(SettlementEntry).where(SettlementEntry.kind == "adjustment")))
    assert total == -95_000


def test_rejecting_a_proposal_returns_to_discussion(scene, oid):  # noqa: F811
    s = scene
    claim = _claim(s, oid).json()["data"]
    _respond(s, "merchant", claim["id"], "proposal", "Penjelasan saja", {"remedy_type": "explanation"})
    rid = s.client.get(f"{API}/claims/{claim['id']}", headers=s.h["buyer"]).json()["data"]["responses"][-1]["id"]
    out = s.client.post(f"{API}/claims/{claim['id']}/proposals/{rid}/decision", headers=s.h["buyer"],
                        json={"decision": "reject"}).json()["data"]
    assert out["status"] == "partner_discussion"


def test_buyer_can_withdraw_an_open_claim(scene, oid):  # noqa: F811
    s = scene
    claim = _claim(s, oid).json()["data"]
    out = s.client.post(f"{API}/claims/{claim['id']}/withdraw", headers=s.h["buyer"]).json()["data"]
    assert out["status"] == "withdrawn"
    assert s.client.post(f"{API}/claims/{claim['id']}/withdraw", headers=s.h["buyer"]).status_code == 409
    assert _claim(s, oid).status_code == 201  # a new claim can be opened afterwards


# ---------- appeal + internal review ----------

def test_appeal_requires_a_recorded_rejection(scene, oid):  # noqa: F811
    s = scene
    claim = _claim(s, oid).json()["data"]
    early = _appeal(s, claim["id"], str(uuid.uuid4()))
    assert early.status_code == 409 and early.json()["error"]["code"] == "invalid_transition"
    rejection = _reject(s, claim["id"])
    assert _appeal(s, claim["id"], str(uuid.uuid4())).status_code == 422
    assert s.client.post(f"{API}/claims/{claim['id']}/appeals", headers=s.h["merchant"],
                         json={"partner_rejection_id": rejection, "reason": "tidak boleh"}).status_code == 403
    ok = _appeal(s, claim["id"], rejection)
    assert ok.status_code == 201 and ok.json()["data"]["status"] == "pending"
    assert s.client.get(f"{API}/claims/{claim['id']}", headers=s.h["buyer"]).json()["data"]["status"] == "appealed"
    assert _appeal(s, claim["id"], rejection).status_code == 409


def _appealed(s, oid, files=()):
    claim = _claim(s, oid, files=files).json()["data"]
    rejection = _reject(s, claim["id"])
    appeal = _appeal(s, claim["id"], rejection).json()["data"]
    return claim, appeal


def test_review_queue_is_admin_only_and_party_cannot_review(scene, oid, make_user, auth_header):  # noqa: F811
    s = scene
    _, appeal = _appealed(s, oid)
    assert s.client.get(f"{API}/admin/appeals", headers=s.h["buyer"]).status_code == 403
    queue = s.client.get(f"{API}/admin/appeals?status=pending", headers=s.h["admin"]).json()["data"]["items"]
    assert [a["id"] for a in queue] == [appeal["id"]]
    s.session.add(__import__("app.models", fromlist=["RoleAssignment"]).RoleAssignment(
        user_id=s.merchant.id, role="admin", status="active"))
    s.session.flush()
    r = s.client.post(f"{API}/admin/appeals/{appeal['id']}/start-review", headers=s.h["merchant"])
    assert r.status_code == 403  # the responsible partner cannot review their own case


def test_reviewer_joins_the_claim_discussion_and_sees_a_scoped_bundle(scene, oid, evidence, storage):  # noqa: F811
    s = scene
    app.dependency_overrides[get_storage] = lambda: storage
    claim, appeal = _appealed(s, oid, files=[evidence])
    assert s.client.get(f"{API}/admin/appeals/{appeal['id']}", headers=s.h["admin"]).status_code == 403
    assert s.client.get(f"{API}/conversations/{claim['conversation_id']}/messages",
                        headers=s.h["admin"]).status_code == 404  # not a member yet
    started = s.client.post(f"{API}/admin/appeals/{appeal['id']}/start-review", headers=s.h["admin"])
    assert started.json()["data"]["status"] == "under_review"
    assert s.client.get(f"{API}/conversations/{claim['conversation_id']}/messages",
                        headers=s.h["admin"]).status_code == 200
    bundle = s.client.get(f"{API}/admin/appeals/{appeal['id']}", headers=s.h["admin"]).json()["data"]
    snap = bundle["order"]["approved_snapshot"]
    assert "measurements_cm" not in snap and "address" not in snap
    assert "design_state" in snap["specification"]  # the approved design is the evidence in a dispute
    assert bundle["order_events"][0]["type"] == "order_confirmed"
    assert {s_["leg"] for s_ in bundle["shipments"]} == {"merchant_to_tailor", "tailor_to_buyer"}
    assert bundle["claim"]["evidence"][0]["url"]
    actions = {e.action for e in s.session.scalars(select(AuditEvent))}
    assert {"claim.review_started", "claim.evidence_viewed"} <= actions


def test_reviewer_can_request_more_evidence(scene, oid):  # noqa: F811
    s = scene
    claim, appeal = _appealed(s, oid)
    s.client.post(f"{API}/admin/appeals/{appeal['id']}/start-review", headers=s.h["admin"])
    r = s.client.post(f"{API}/admin/appeals/{appeal['id']}/request-evidence", headers=s.h["admin"],
                      json={"message": "Mohon foto saku dari jarak dekat"})
    assert r.status_code == 201
    msgs = s.client.get(f"{API}/conversations/{claim['conversation_id']}/messages",
                        headers=s.h["buyer"]).json()["data"]["items"]
    assert "Permintaan bukti reviewer" in msgs[-1]["body"]


def test_upholding_the_rejection_resolves_the_claim(scene, oid):  # noqa: F811
    s = scene
    claim, appeal = _appealed(s, oid)
    s.client.post(f"{API}/admin/appeals/{appeal['id']}/start-review", headers=s.h["admin"])
    assert _decide(s, appeal["id"], outcome="upheld_rejection", remedy_type="refund_partial").status_code == 422
    r = _decide(s, appeal["id"], outcome="upheld_rejection", remedy_type="none", amount_idr=None)
    assert r.status_code == 200 and r.json()["data"]["requires_execution"] is False
    detail = s.client.get(f"{API}/claims/{claim['id']}", headers=s.h["buyer"]).json()["data"]
    assert detail["status"] == "resolved" and detail["decision"]["outcome"] == "upheld_rejection"
    assert "Bukti menunjukkan" in detail["decision"]["reasoning"]


def test_overturning_needs_a_remedy_and_reasoning(scene, oid):  # noqa: F811
    s = scene
    _, appeal = _appealed(s, oid)
    s.client.post(f"{API}/admin/appeals/{appeal['id']}/start-review", headers=s.h["admin"])
    assert _decide(s, appeal["id"], remedy_type="none", amount_idr=None).status_code == 422
    assert _decide(s, appeal["id"], reasoning="x").status_code == 422
    assert _decide(s, appeal["id"], amount_idr=99_999_999).status_code == 422  # beyond the order total
    assert _decide(s, appeal["id"], who="buyer").status_code == 403


def test_only_the_assigned_reviewer_decides(scene, oid, make_user, auth_header):  # noqa: F811
    s = scene
    _, appeal = _appealed(s, oid)
    other_admin = make_user("admin2@example.com", roles=(("admin", "active"),))
    s.h["admin2"] = auth_header(other_admin)
    assert _decide(s, appeal["id"]).status_code == 403  # review not started
    s.client.post(f"{API}/admin/appeals/{appeal['id']}/start-review", headers=s.h["admin"])
    assert _decide(s, appeal["id"], who="admin2").status_code == 403
    assert s.client.get(f"{API}/admin/appeals/{appeal['id']}", headers=s.h["admin2"]).status_code == 403


def test_overturned_decision_is_executed_separately_then_resolves(scene, oid):  # noqa: F811
    s = scene
    claim, appeal = _appealed(s, oid)
    s.client.post(f"{API}/admin/appeals/{appeal['id']}/start-review", headers=s.h["admin"])
    decided = _decide(s, appeal["id"]).json()["data"]
    assert decided["requires_execution"] is True
    mid = s.client.get(f"{API}/claims/{claim['id']}", headers=s.h["buyer"]).json()["data"]
    assert mid["status"] == "decision_issued" and mid["remedy_events"] == []
    assert s.client.post(f"{API}/claims/{claim['id']}/remedy-events", headers=s.h["merchant"],
                         json={"action": "refund_partial", "amount_idr": 100_000}).status_code == 403
    r = s.client.post(f"{API}/claims/{claim['id']}/remedy-events", headers=s.h["admin"],
                      json={"action": "refund_partial", "amount_idr": 100_000, "note": "Refund simulasi"})
    assert r.status_code == 201 and r.json()["data"]["claim_status"] == "resolved"
    final = s.client.get(f"{API}/claims/{claim['id']}", headers=s.h["buyer"]).json()["data"]
    assert final["decision"]["amount_idr"] == 100_000 and final["remedy_events"][0]["amount_idr"] == 100_000
    again = s.client.post(f"{API}/claims/{claim['id']}/remedy-events", headers=s.h["admin"],
                          json={"action": "refund_partial", "amount_idr": 100_000})
    assert again.status_code == 409  # a remedy is never executed twice
    adjustments = list(s.session.scalars(select(SettlementEntry).where(SettlementEntry.kind == "adjustment")))
    assert len(adjustments) == 1
    actions = {e.action for e in s.session.scalars(select(AuditEvent))}
    assert {"claim.decided", "claim.remedy_executed"} <= actions


# ---------- claims block completion ----------

def _deliver(s, oid):
    _event(s, "merchant", oid, "start_preparing")
    _event(s, "merchant", oid, "dispatch_to_tailor")
    _event(s, "tailor", oid, "receive_fabric")
    _inspect(s, oid)
    _event(s, "tailor", oid, "begin_production")
    _event(s, "tailor", oid, "complete_production", "QC lulus")
    _event(s, "tailor", oid, "dispatch_finished")
    _event(s, "admin", oid, "simulate_delivery")


def test_open_claim_blocks_completion_until_it_is_handled(scene, oid):  # noqa: F811
    s = scene
    _deliver(s, oid)
    claim = _claim(s, oid, "tailor", "garment").json()["data"]
    blocked = _event(s, "buyer", oid, "confirm_receipt")
    assert blocked.status_code == 409 and "klaim" in blocked.json()["error"]["message"].lower()
    s.client.post(f"{API}/claims/{claim['id']}/withdraw", headers=s.h["buyer"])
    assert _event(s, "buyer", oid, "confirm_receipt").json()["data"]["status"] == "completed"


def test_claims_can_still_be_opened_after_completion(scene, oid):  # noqa: F811
    s = scene
    _deliver(s, oid)
    _event(s, "buyer", oid, "confirm_receipt")
    assert _claim(s, oid, "tailor", "garment").status_code == 201


# ---------- privacy + admin audit ----------

def test_users_can_list_and_delete_their_own_private_files(scene, make_file, storage):  # noqa: F811
    s = scene
    app.dependency_overrides[get_storage] = lambda: storage
    f = make_file(s.buyer)
    listed = s.client.get(f"{API}/me/files", headers=s.h["buyer"]).json()["data"]
    assert [x["id"] for x in listed] == [str(f.id)]
    assert s.client.delete(f"{API}/files/{f.id}", headers=s.h["merchant"]).status_code == 404
    assert s.client.delete(f"{API}/files/{f.id}", headers=s.h["buyer"]).status_code == 200
    assert s.client.get(f"{API}/me/files", headers=s.h["buyer"]).json()["data"] == []
    assert s.client.delete(f"{API}/files/{f.id}", headers=s.h["buyer"]).status_code == 404


def test_evidence_of_an_open_claim_cannot_be_deleted(scene, oid, evidence, storage):  # noqa: F811
    s = scene
    app.dependency_overrides[get_storage] = lambda: storage
    claim = _claim(s, oid, files=[evidence]).json()["data"]
    assert s.client.delete(f"{API}/files/{evidence.id}", headers=s.h["buyer"]).status_code == 409
    s.client.post(f"{API}/claims/{claim['id']}/withdraw", headers=s.h["buyer"])
    assert s.client.delete(f"{API}/files/{evidence.id}", headers=s.h["buyer"]).status_code == 200


def test_deleting_a_file_does_not_erase_the_approved_order(scene, oid, make_file, storage):  # noqa: F811
    s = scene
    app.dependency_overrides[get_storage] = lambda: storage
    f = make_file(s.buyer)
    before = s.client.get(f"{API}/orders/{oid}", headers=s.h["buyer"]).json()["data"]
    s.client.delete(f"{API}/files/{f.id}", headers=s.h["buyer"])
    after = s.client.get(f"{API}/orders/{oid}", headers=s.h["buyer"]).json()["data"]
    assert before["snapshot"] == after["snapshot"] and after["total_idr"] == before["total_idr"]


def test_audit_trail_is_admin_only_and_filterable(scene, oid):  # noqa: F811
    s = scene
    claim = _claim(s, oid).json()["data"]
    assert s.client.get(f"{API}/admin/audit-events", headers=s.h["buyer"]).status_code == 403
    items = s.client.get(f"{API}/admin/audit-events?action=claim.opened&target_id={claim['id']}",
                         headers=s.h["admin"]).json()["data"]["items"]
    assert len(items) == 1 and items[0]["actor_user_id"] == str(s.buyer.id)
    assert items[0]["metadata"]["target"] == "merchant"
