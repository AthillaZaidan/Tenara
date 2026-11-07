import uuid

import pytest

from app.services import gallery as svc
from app.services.files import create_file
from app.services.storage import LocalDiskStorage

API = "/api/v1"


@pytest.fixture
def admin(make_user):
    return make_user("admin@example.com", roles=(("admin", "active"),))


@pytest.fixture
def ah(admin, auth_header):
    return auth_header(admin)


def _post(client, url, headers, **json):
    return client.post(f"{API}{url}", headers=headers, json=json)


def _entry(client, ah, **extra):
    body = {"name": "Tenun Ikat Sumba", "region": "NTT", "technique": "Tenun ikat",
            "aliases": ["Hinggi", "Kain Sumba"], "summary": "Tenun ikat dari pulau Sumba."}
    body.update(extra)
    r = _post(client, "/admin/gallery", ah, **body)
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _source(client, ah, approve=True):
    r = _post(client, "/admin/sources", ah, title="Dataset motif", publisher="Univ",
              license="CC BY 4.0")
    sid = r.json()["data"]["id"]
    if approve:
        assert _post(client, f"/admin/sources/{sid}/decision", ah, decision="approve").status_code == 200
    return sid


def _approved_story(client, ah, entry_id, source_id, body="Motif kuda melambangkan keberanian."):
    r = _post(client, f"/admin/gallery/{entry_id}/stories", ah, body=body,
              citations=[{"source_id": source_id, "locator": "row 3"}],
              unresolved=["asal-usul motif"])
    assert r.status_code == 201, r.text
    sid = r.json()["data"]["id"]
    assert _post(client, f"/admin/stories/{sid}/submit", ah).status_code == 200
    r = _post(client, f"/admin/stories/{sid}/decision", ah, decision="approve")
    assert r.status_code == 200, r.text
    return sid


def _published(client, ah, **extra):
    entry = _entry(client, ah, **extra)
    source = _source(client, ah)
    _approved_story(client, ah, entry["id"], source)
    r = _post(client, f"/admin/gallery/{entry['id']}/publish", ah)
    assert r.status_code == 200, r.text
    return entry["id"], source


# ---- access ----

def test_admin_endpoints_require_admin(client, make_user, auth_header):
    buyer = make_user("b@example.com")
    assert client.post(f"{API}/admin/gallery", json={"name": "x"}).status_code == 401
    r = client.post(f"{API}/admin/gallery", headers=auth_header(buyer), json={"name": "x"})
    assert r.status_code == 403


# ---- curation rules ----

def test_draft_entry_is_not_public(client, ah):
    entry = _entry(client, ah)
    assert entry["status"] == "draft"
    assert client.get(f"{API}/gallery/{entry['id']}").status_code == 404
    assert client.get(f"{API}/gallery").json()["data"]["items"] == []


def test_publish_needs_approved_story(client, ah):
    entry = _entry(client, ah)
    r = _post(client, f"/admin/gallery/{entry['id']}/publish", ah)
    assert r.status_code == 422
    assert r.json()["error"]["field"] == "story"


def test_story_cannot_be_approved_with_unapproved_source(client, ah):
    entry, source = _entry(client, ah), _source(client, ah, approve=False)
    r = _post(client, f"/admin/gallery/{entry['id']}/stories", ah, body="Klaim.",
              citations=[{"source_id": source}])
    sid = r.json()["data"]["id"]
    _post(client, f"/admin/stories/{sid}/submit", ah)
    r = _post(client, f"/admin/stories/{sid}/decision", ah, decision="approve")
    assert r.status_code == 422
    assert r.json()["error"]["field"] == "citations"


def test_story_without_citations_cannot_be_approved(client, ah):
    entry = _entry(client, ah)
    sid = _post(client, f"/admin/gallery/{entry['id']}/stories", ah, body="Tanpa sitasi.").json()["data"]["id"]
    _post(client, f"/admin/stories/{sid}/submit", ah)
    r = _post(client, f"/admin/stories/{sid}/decision", ah, decision="approve")
    assert r.status_code == 422


def test_story_with_unknown_source_is_rejected(client, ah):
    entry = _entry(client, ah)
    r = _post(client, f"/admin/gallery/{entry['id']}/stories", ah, body="x",
              citations=[{"source_id": str(uuid.uuid4())}])
    assert r.status_code == 422


def test_reject_story_requires_reason(client, ah):
    entry = _entry(client, ah)
    sid = _post(client, f"/admin/gallery/{entry['id']}/stories", ah, body="x").json()["data"]["id"]
    _post(client, f"/admin/stories/{sid}/submit", ah)
    assert _post(client, f"/admin/stories/{sid}/decision", ah, decision="reject").status_code == 422
    r = _post(client, f"/admin/stories/{sid}/decision", ah, decision="reject", reason="Tidak ada bukti")
    assert r.json()["data"]["status"] == "rejected"


def test_new_revision_supersedes_previous(client, ah):
    entry_id, source = _published(client, ah)
    _approved_story(client, ah, entry_id, source, body="Revisi kedua tentang kuda dan status.")
    stories = client.get(f"{API}/admin/gallery/{entry_id}/stories", headers=ah).json()["data"]
    assert [s["status"] for s in stories] == ["approved", "superseded"]
    passport = client.get(f"{API}/gallery/{entry_id}/passport").json()["data"]
    assert passport["story"]["revision"] == 2


def test_cannot_reject_source_cited_by_published_content(client, ah):
    _, source = _published(client, ah)
    r = _post(client, f"/admin/sources/{source}/decision", ah, decision="reject", reason="salah")
    assert r.status_code == 422


def test_reject_source_requires_reason(client, ah):
    source = _source(client, ah, approve=False)
    assert _post(client, f"/admin/sources/{source}/decision", ah, decision="reject").status_code == 422


def test_update_entry_checks_revision(client, ah):
    entry = _entry(client, ah)
    ok = client.patch(f"{API}/admin/gallery/{entry['id']}", headers=ah,
                      json={"expected_revision": entry["revision"], "summary": "baru"})
    assert ok.status_code == 200 and ok.json()["data"]["revision"] == entry["revision"] + 1
    stale = client.patch(f"{API}/admin/gallery/{entry['id']}", headers=ah,
                         json={"expected_revision": entry["revision"], "summary": "lama"})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "stale_revision"


def test_archive_hides_entry(client, ah):
    entry_id, _ = _published(client, ah)
    assert client.get(f"{API}/gallery/{entry_id}").status_code == 200
    _post(client, f"/admin/gallery/{entry_id}/archive", ah)
    assert client.get(f"{API}/gallery/{entry_id}").status_code == 404


def test_slugs_are_unique(client, ah):
    a, b = _entry(client, ah), _entry(client, ah)
    assert a["slug"] == "tenun-ikat-sumba" and b["slug"] == "tenun-ikat-sumba-2"


# ---- public views ----

def test_published_entry_visible_by_id_and_slug(client, ah):
    entry_id, _ = _published(client, ah)
    by_id = client.get(f"{API}/gallery/{entry_id}").json()["data"]
    by_slug = client.get(f"{API}/gallery/tenun-ikat-sumba").json()["data"]
    assert by_id["id"] == by_slug["id"] == entry_id
    assert by_id["has_story"] is True


def test_list_filters_and_pagination(client, ah):
    for i in range(3):
        _published(client, ah, name=f"Entri {i}", region="NTT" if i < 2 else "Bali")
    items = client.get(f"{API}/gallery?region=ntt").json()["data"]["items"]
    assert len(items) == 2
    page1 = client.get(f"{API}/gallery?limit=2").json()["data"]
    assert len(page1["items"]) == 2 and page1["next_cursor"]
    page2 = client.get(f"{API}/gallery?limit=2&cursor={page1['next_cursor']}").json()["data"]
    assert len(page2["items"]) == 1 and page2["next_cursor"] is None


def test_passport_contains_citations_and_no_private_data(client, ah):
    entry_id, source = _published(client, ah)
    p = client.get(f"{API}/gallery/{entry_id}/passport").json()["data"]
    assert p["citations"][0]["source_id"] == source
    assert p["citations"][0]["license"] == "CC BY 4.0"
    assert p["story"]["unresolved"] == ["asal-usul motif"]
    assert p["review"]["status"] == "reviewed"
    assert "does not certify" in p["notice"]
    text = str(p)
    assert "email" not in text and "password" not in text


def test_reference_images_must_be_public_files(client, session, ah, admin, tmp_path):
    entry = _entry(client, ah)
    storage = LocalDiskStorage(tmp_path)
    private = create_file(session, storage, owner_id=admin.id, kind="ref", data=b"x",
                          content_type="image/png")
    public = create_file(session, storage, owner_id=admin.id, kind="ref", data=b"x",
                         content_type="image/png", visibility="public")
    r = _post(client, f"/admin/gallery/{entry['id']}/images", ah, file_id=str(private.id))
    assert r.status_code == 422
    r = _post(client, f"/admin/gallery/{entry['id']}/images", ah, file_id=str(public.id),
              credit="Dataset", license="CC BY 4.0")
    assert r.status_code == 201
    _approved_story(client, ah, entry["id"], _source(client, ah))
    _post(client, f"/admin/gallery/{entry['id']}/publish", ah)
    images = client.get(f"{API}/gallery/{entry['id']}").json()["data"]["reference_images"]
    assert images[0]["url"] == f"/api/v1/files/{public.id}"


# ---- service-level: audit trail ----

def test_publish_is_audited(client, session, ah):
    from sqlalchemy import select

    from app.models import AuditEvent

    entry_id, _ = _published(client, ah)
    actions = {e.action for e in session.scalars(select(AuditEvent))}
    assert {"gallery.entry_created", "story.approved", "gallery.published",
            "source.approved"} <= actions
    assert svc.get_entry(session, uuid.UUID(entry_id)).status == "published"
