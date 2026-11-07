import pytest
from sqlalchemy import select

from app.models import AuditEvent, RoleAssignment

API = "/api/v1"

MERCHANT_DATA = {"shop_name": "Toko Tenun Sumba", "description": "Kain tenun asli",
                 "city": "Waingapu", "province": "NTT", "contact_phone": "0812"}


@pytest.fixture
def admin(make_user):
    return make_user("admin@example.com", roles=(("admin", "active"),))


@pytest.fixture
def apply_as(client, make_file, auth_header):
    """Create and submit an application for `user`. Returns the application dict."""
    def _apply(user, kind="merchant", data=None, submit=True):
        evidence = make_file(user)
        body = {**(data or MERCHANT_DATA), "evidence_file_ids": [str(evidence.id)]}
        if kind == "tailor":
            body.setdefault("service_area", ["Jawa Barat"])
        r = client.post(f"{API}/partner-applications", headers=auth_header(user),
                        json={"type": kind, "data": body})
        assert r.status_code == 201, r.text
        app = r.json()["data"]
        if submit:
            r = client.post(f"{API}/partner-applications/{app['id']}/submit",
                            headers=auth_header(user))
            assert r.status_code == 200, r.text
            app = r.json()["data"]
        return app

    return _apply


def _decide(client, headers, app_id, action, reason=None):
    return client.post(f"{API}/admin/partner-applications/{app_id}/decision", headers=headers,
                       json={"action": action, "reason": reason})


def test_full_merchant_verification_flow(client, session, make_user, admin, auth_header, apply_as):
    user = make_user("ana@example.com")
    app = apply_as(user)
    assert app["status"] == "submitted"
    role = session.scalar(select(RoleAssignment).where(
        RoleAssignment.user_id == user.id, RoleAssignment.role == "merchant"))
    assert role.status == "pending"
    # pending merchants cannot work yet
    r = client.get(f"{API}/merchant/listings", headers=auth_header(user))
    assert r.status_code == 403
    ah = auth_header(admin)
    assert _decide(client, ah, app["id"], "start_review").json()["data"]["status"] == "under_review"
    assert _decide(client, ah, app["id"], "approve").json()["data"]["status"] == "approved"
    assert client.get(f"{API}/merchant/listings", headers=auth_header(user)).status_code == 200
    session.refresh(role)
    assert role.status == "active" and role.decided_by == admin.id


def test_public_merchant_profile_after_approval(client, session, make_user, admin, auth_header, apply_as):
    from app.models import MerchantProfile

    user = make_user("ana@example.com")
    app = apply_as(user)
    _decide(client, auth_header(admin), app["id"], "approve")
    profile = session.scalar(select(MerchantProfile).where(MerchantProfile.user_id == user.id))
    data = client.get(f"{API}/merchants/{profile.id}").json()["data"]
    assert data["shop_name"] == "Toko Tenun Sumba" and data["verified"] is True
    assert "bukan sertifikasi" in data["verification_note"]
    assert "contact_phone" not in data


def test_reject_requires_reason_and_removes_pending_role(client, session, make_user, admin, auth_header, apply_as):
    user = make_user("ana@example.com")
    app = apply_as(user)
    ah = auth_header(admin)
    assert _decide(client, ah, app["id"], "reject").status_code == 422
    assert _decide(client, ah, app["id"], "reject", "Bukti tidak jelas").status_code == 200
    assert session.scalar(select(RoleAssignment).where(
        RoleAssignment.user_id == user.id, RoleAssignment.role == "merchant")) is None
    # a rejected applicant may apply again
    again = apply_as(user)
    assert again["status"] == "submitted"


def test_request_information_then_resubmit(client, make_user, admin, auth_header, apply_as, make_file):
    user = make_user("ana@example.com")
    app = apply_as(user)
    ah, uh = auth_header(admin), auth_header(user)
    assert _decide(client, ah, app["id"], "request_information").status_code == 422
    assert _decide(client, ah, app["id"], "request_information", "Lengkapi alamat").status_code == 200
    evidence = make_file(user)
    r = client.patch(f"{API}/partner-applications/{app['id']}", headers=uh,
                     json={"data": {**MERCHANT_DATA, "city": "Kupang",
                                    "evidence_file_ids": [str(evidence.id)]}})
    assert r.status_code == 200
    assert client.post(f"{API}/partner-applications/{app['id']}/submit", headers=uh).status_code == 200
    assert _decide(client, ah, app["id"], "approve").status_code == 200


def test_cannot_decide_before_submit_or_twice(client, make_user, admin, auth_header, apply_as):
    user = make_user("ana@example.com")
    draft = apply_as(user, submit=False)
    ah = auth_header(admin)
    assert _decide(client, ah, draft["id"], "approve").status_code == 422
    client.post(f"{API}/partner-applications/{draft['id']}/submit", headers=auth_header(user))
    assert _decide(client, ah, draft["id"], "approve").status_code == 200
    assert _decide(client, ah, draft["id"], "approve").status_code == 422


def test_submit_requires_own_evidence(client, make_user, make_file, auth_header):
    ana, bob = make_user("ana@example.com"), make_user("bob@example.com")
    stolen = make_file(bob)
    r = client.post(f"{API}/partner-applications", headers=auth_header(ana),
                    json={"type": "merchant",
                          "data": {**MERCHANT_DATA, "evidence_file_ids": [str(stolen.id)]}})
    app_id = r.json()["data"]["id"]
    r = client.post(f"{API}/partner-applications/{app_id}/submit", headers=auth_header(ana))
    assert r.status_code == 422
    # no evidence at all
    r = client.post(f"{API}/partner-applications", headers=auth_header(bob),
                    json={"type": "merchant", "data": MERCHANT_DATA})
    r = client.post(f"{API}/partner-applications/{r.json()['data']['id']}/submit",
                    headers=auth_header(bob))
    assert r.status_code == 422


def test_invalid_application_data_is_rejected(client, make_user, auth_header):
    r = client.post(f"{API}/partner-applications", headers=auth_header(make_user()),
                    json={"type": "merchant", "data": {"shop_name": ""}})
    assert r.status_code == 422


def test_only_one_open_application_per_type(client, make_user, auth_header, apply_as):
    user = make_user("ana@example.com")
    apply_as(user)
    r = client.post(f"{API}/partner-applications", headers=auth_header(user),
                    json={"type": "merchant", "data": MERCHANT_DATA})
    assert r.status_code == 422


def test_applications_are_private(client, make_user, auth_header, apply_as):
    ana, bob = make_user("ana@example.com"), make_user("bob@example.com")
    app = apply_as(ana)
    r = client.post(f"{API}/partner-applications/{app['id']}/submit", headers=auth_header(bob))
    assert r.status_code == 404
    assert client.get(f"{API}/partner-applications/mine", headers=auth_header(bob)).json()["data"] == []


def test_admin_endpoints_are_admin_only(client, make_user, auth_header, apply_as):
    user = make_user("ana@example.com")
    app = apply_as(user)
    assert client.get(f"{API}/admin/partner-applications", headers=auth_header(user)).status_code == 403
    assert _decide(client, auth_header(user), app["id"], "approve").status_code == 403


def test_admin_viewing_evidence_is_audited_and_signed(client, session, make_user, admin, auth_header, apply_as, storage):
    from app.main import app as fastapi_app
    from app.services.storage import get_storage

    fastapi_app.dependency_overrides[get_storage] = lambda: storage
    app = apply_as(make_user("ana@example.com"))
    r = client.get(f"{API}/admin/partner-applications/{app['id']}", headers=auth_header(admin))
    evidence = r.json()["data"]["evidence"]
    assert evidence and "token=" in evidence[0]["url"]
    assert client.get(evidence[0]["url"]).status_code == 200
    actions = {e.action for e in session.scalars(select(AuditEvent))}
    assert "partner.evidence_viewed" in actions


def test_suspend_and_reinstate(client, session, make_user, admin, auth_header, apply_as):
    user = make_user("ana@example.com")
    app = apply_as(user)
    ah = auth_header(admin)
    _decide(client, ah, app["id"], "approve")
    body = {"user_id": str(user.id), "role": "merchant"}
    assert client.post(f"{API}/admin/partners/suspend", headers=ah, json=body).status_code == 422
    r = client.post(f"{API}/admin/partners/suspend", headers=ah, json={**body, "reason": "Laporan penipuan"})
    assert r.status_code == 200
    assert client.get(f"{API}/merchant/listings", headers=auth_header(user)).status_code == 403
    assert client.post(f"{API}/admin/partners/reinstate", headers=ah, json=body).status_code == 200
    assert client.get(f"{API}/merchant/listings", headers=auth_header(user)).status_code == 200


# ---------- tailor ----------

TAILOR_CAP = {"base_rate_idr": 350000, "lead_time_days": 14, "weekly_capacity": 3,
              "materials": ["tenun ikat"], "supported_options": {"pocket": ["left_chest_single"]}}


def test_tailor_onboarding_and_capabilities(client, session, make_user, admin, auth_header, apply_as):
    user = make_user("tailor@example.com")
    app = apply_as(user, "tailor", {"shop_name": "Penjahit Rina", "city": "Bandung",
                                    "province": "Jawa Barat", "experience_years": 8})
    uh = auth_header(user)
    assert client.get(f"{API}/tailor/capabilities", headers=uh).status_code == 403  # still pending
    _decide(client, auth_header(admin), app["id"], "approve")
    r = client.put(f"{API}/tailor/capabilities/T01", headers=uh, json=TAILOR_CAP)
    assert r.status_code == 200 and r.json()["data"]["rate_version"] == 1
    cheaper = client.put(f"{API}/tailor/capabilities/T01", headers=uh,
                         json={**TAILOR_CAP, "base_rate_idr": 300000})
    assert cheaper.json()["data"]["rate_version"] == 2
    same = client.put(f"{API}/tailor/capabilities/T01", headers=uh,
                      json={**TAILOR_CAP, "base_rate_idr": 300000, "lead_time_days": 10})
    assert same.json()["data"]["rate_version"] == 2
    assert client.put(f"{API}/tailor/capabilities/T09", headers=uh, json=TAILOR_CAP).status_code == 422
    assert client.put(f"{API}/tailor/capabilities/T02", headers=uh,
                      json={**TAILOR_CAP, "base_rate_idr": 0}).status_code == 422
    assert len(client.get(f"{API}/tailor/capabilities", headers=uh).json()["data"]) == 1


def test_public_tailor_profile_shows_rates(client, session, make_user, admin, auth_header, apply_as):
    from app.models import TailorProfile

    user = make_user("tailor@example.com")
    app = apply_as(user, "tailor", {"shop_name": "Penjahit Rina", "city": "Bandung",
                                    "province": "Jawa Barat"})
    _decide(client, auth_header(admin), app["id"], "approve")
    client.put(f"{API}/tailor/capabilities/T03", headers=auth_header(user), json=TAILOR_CAP)
    profile = session.scalar(select(TailorProfile).where(TailorProfile.user_id == user.id))
    data = client.get(f"{API}/tailors/{profile.id}").json()["data"]
    assert data["service_area"] == ["Jawa Barat"]
    assert data["capabilities"][0]["template_code"] == "T03"
    assert data["capabilities"][0]["base_rate_idr"] == 350000


def test_delete_capability(client, make_partner, auth_header):
    user, _ = make_partner("tailor", shop="Penjahit A")
    uh = auth_header(user)
    client.put(f"{API}/tailor/capabilities/T01", headers=uh, json=TAILOR_CAP)
    assert client.delete(f"{API}/tailor/capabilities/T01", headers=uh).status_code == 200
    assert client.delete(f"{API}/tailor/capabilities/T01", headers=uh).status_code == 404
