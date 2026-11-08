"""Photo check of a seller's tradition claim against curator-approved reference photos."""
import io

import numpy as np
import pytest
from PIL import Image
from sqlalchemy import select
from test_ai import FakeVLM, _analyze, _fabric_png, ai, seller  # noqa: F401  (shared scan fixtures)
from test_customization import entry, make_listing  # noqa: F401

from app.ml.vision import photo_match
from app.ml.vision.photo_match import FakePhotoEmbedder, check_claim
from app.models import AuditEvent, GalleryEntry, ReferencePhoto
from app.services import gallery as gallery_svc
from app.services.files import create_file

API = "/api/v1"
RED, BLUE, PURPLE = (200, 40, 40), (40, 40, 200), (200, 40, 200)


def _img(color, seed, noise=70) -> bytes:
    """A noisy colour field: same colour ~0.89 similar under the fake embedder, other colours far."""
    rng = np.random.default_rng(seed)
    a = np.clip(np.array(color) + rng.integers(-noise, noise, (16, 16, 3)), 0, 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(a).resize((64, 64), Image.NEAREST).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def emb():
    return FakePhotoEmbedder()


@pytest.fixture
def tradition(session):
    def _make(name):
        return gallery_svc.create_entry(session, None, name=name, technique="Tenun ikat", region="NTT")
    return _make


def _refs(session, emb, entry, color, n, sources=("a", "b"), style="modern", status="approved",
          seed=0, **extra):
    out = []
    for i in range(n):
        ref = photo_match.add_reference(session, emb, entry=entry, image=_img(color, seed + i),
                                        style=style, source_label=sources[i % len(sources)], **extra)
        ref.approval_status = status
        out.append(ref)
    session.flush()
    return out


@pytest.fixture
def two_traditions(session, emb, tradition):
    sumba, sikka = tradition("Tenun Ikat Sumba"), tradition("Tenun Ikat Sikka")
    _refs(session, emb, sumba, RED, 6, seed=100)
    _refs(session, emb, sikka, BLUE, 6, seed=200)
    return sumba, sikka


def test_true_claim_is_consistent_and_false_claim_needs_a_check(session, emb, two_traditions):
    sumba, sikka = two_traditions
    photo = _img(RED, 999)
    ok = check_claim(session, emb, photo, sumba)
    assert ok["status"] == "konsisten" and ok["rank"] == 1 and "bukan verifikasi" in ok["message"]
    assert ok["top"][0]["tradition"] == "Tenun Ikat Sumba"
    bad = check_claim(session, emb, photo, sikka)
    assert bad["status"] == "perlu_dicek" and bad["rank"] == 2
    assert bad["claimed"] == "Tenun Ikat Sikka"


def test_too_few_references_or_one_source_means_no_verdict(session, emb, two_traditions, tradition):
    few, single = tradition("Songket Palembang"), tradition("Ulos Batak Toba")
    _refs(session, emb, few, PURPLE, photo_match.MIN_REFS - 1, seed=300)
    _refs(session, emb, single, PURPLE, 8, sources=("satu-sumber",), seed=400)
    for entry_ in (few, single):
        out = check_claim(session, emb, _img(PURPLE, 998), entry_)
        assert out["status"] == "belum_ada_referensi" and out["rank"] is None and out["top"] == []
        assert "minimal" in out["message"]


def test_pending_rejected_archival_and_other_model_references_give_no_verdict(session, emb, tradition):
    lurik = tradition("Lurik")
    _refs(session, emb, lurik, RED, 6, status="pending", seed=1)
    _refs(session, emb, lurik, RED, 6, status="rejected", seed=20)
    _refs(session, emb, lurik, RED, 6, style="archival", seed=40)
    other = _refs(session, emb, lurik, RED, 6, seed=60)
    for ref in other:
        ref.embed_model = "some-other-model"
    session.flush()
    assert check_claim(session, emb, _img(RED, 997), lurik)["status"] == "belum_ada_referensi"


def test_archival_references_are_shown_for_comparison_only_when_allowed(session, emb, two_traditions,
                                                                     storage, make_user):
    sumba, _ = two_traditions
    owner = make_user("refs@example.com")
    for i, allowed in enumerate((True, False)):
        data = _img(RED, 500 + i)
        file = create_file(session, storage, owner_id=owner.id, kind="reference_photo", data=data,
                           content_type="image/png", visibility="public")
        _refs(session, emb, sumba, RED, 1, style="archival", seed=500 + i, file_id=file.id,
              display_allowed=allowed, credit=f"Museum {i}", license="CC0")
    out = check_claim(session, emb, _img(RED, 996), sumba)
    assert [c["credit"] for c in out["comparisons"]] == ["Museum 0"]
    assert out["comparisons"][0]["style"] == "archival" and out["comparisons"][0]["url"].startswith("/api/v1/files/")


def test_a_near_copy_of_a_reference_is_flagged_not_confirmed(session, emb, two_traditions):
    sumba, _ = two_traditions
    copied = _img(RED, 100)  # identical to one of Sumba's reference photos
    out = check_claim(session, emb, copied, sumba)
    assert out["status"] == "perlu_dicek" and out["notes"] and "hampir identik" in out["notes"][0]


def test_switched_off_or_failing_embedder(session, two_traditions):
    sumba, _ = two_traditions
    assert check_claim(session, None, _img(RED, 1), sumba) is None

    class Broken:
        name = "fake-colour-v1"

        def embed(self, image):
            raise RuntimeError("model missing")

    out = check_claim(session, Broken(), _img(RED, 1), sumba)
    assert out["status"] == "gagal" and out["rank"] is None


def test_scan_reports_the_claim_check_for_the_listings_own_entry(client, session, seller, auth_header, emb):
    user, listing = seller
    claimed = session.get(GalleryEntry, listing.entry_id)
    other = gallery_svc.create_entry(session, None, name="Tenun Lain", technique="Tenun ikat", region="NTT")
    # the seller's photo (_fabric_png) is dark red with stripes; reference photos of the claim look alike
    photo = Image.open(io.BytesIO(_fabric_png())).convert("RGB")
    base = tuple(int(x) for x in np.asarray(photo.resize((1, 1)))[0, 0])
    _refs(session, emb, claimed, base, 6, seed=700)
    _refs(session, emb, other, BLUE, 6, seed=800)
    r = _analyze(client, auth_header(user), listing, FakeVLM())
    assert r.status_code == 200, r.text
    check = r.json()["data"]["result"]["claim_check"]
    assert check["claimed"] == claimed.name and check["status"] == "konsisten"
    session.refresh(listing)
    assert listing.visual_match["claim_check"]["status"] == "konsisten"
    assert listing.curator_verified_origin is None  # a signal, never a verification


def test_scan_without_references_says_so(client, session, seller, auth_header, emb):
    user, listing = seller
    check = _analyze(client, auth_header(user), listing, FakeVLM()).json()["data"]["result"]["claim_check"]
    assert check["status"] == "belum_ada_referensi"


def test_curator_verification_can_add_listing_photos_as_hidden_modern_references(
        client, session, seller, auth_header, make_user, emb):
    user, listing = seller
    admin = make_user("curator@example.com", roles=(("admin", "active"),))
    url = f"{API}/admin/listings/{listing.id}/verify-origin"
    assert client.post(url, headers=auth_header(user),
                       json={"text": "Sumba", "add_as_reference": True}).status_code == 403
    r = client.post(url, headers=auth_header(admin), json={"text": "Sumba Timur", "add_as_reference": True})
    assert r.status_code == 200, r.text
    refs = list(session.scalars(select(ReferencePhoto).where(ReferencePhoto.listing_id == listing.id)))
    assert len(refs) == 1
    ref = refs[0]
    assert (ref.style, ref.approval_status, ref.display_allowed, ref.entry_id) == \
        ("modern", "approved", False, listing.entry_id)
    assert ref.source_label == f"merchant:{listing.merchant_id}" and ref.decided_by == admin.id
    client.post(url, headers=auth_header(admin), json={"text": "Sumba Timur", "add_as_reference": True})
    assert session.scalar(select(ReferencePhoto.id).where(ReferencePhoto.listing_id == listing.id)
                          .offset(1)) is None  # idempotent
    # without the flag nothing is added
    session.delete(ref)
    session.flush()
    client.post(url, headers=auth_header(admin), json={"text": "Sumba Timur"})
    assert session.scalar(select(ReferencePhoto.id).where(ReferencePhoto.listing_id == listing.id)) is None


def test_admin_reviews_reference_photos_by_source_and_sees_coverage(client, session, emb, tradition,
                                                                     make_user, auth_header):
    sumba = tradition("Tenun Ikat Sumba")
    _refs(session, emb, sumba, RED, 4, sources=("museum-a",), status="pending", seed=1)
    _refs(session, emb, sumba, RED, 3, sources=("foto-tim",), status="pending", seed=10)
    admin = auth_header(make_user("curator@example.com", roles=(("admin", "active"),)))
    buyer = auth_header(make_user("buyer@example.com"))
    assert client.get(f"{API}/admin/reference-photos", headers=buyer).status_code == 403

    page = client.get(f"{API}/admin/reference-photos?approval_status=pending&limit=5", headers=admin).json()["data"]
    assert len(page["items"]) == 5 and page["next_cursor"]
    assert page["items"][0]["tradition"] == "Tenun Ikat Sumba"

    r = client.post(f"{API}/admin/reference-photos/decision", headers=admin,
                    json={"decision": "approve", "source_label": "museum-a"})
    assert r.json()["data"]["updated"] == 4
    cov = client.get(f"{API}/admin/reference-photos/coverage", headers=admin).json()["data"]
    item = cov["items"][0]
    assert (item["modern_approved"], item["modern_sources"], item["pending"], item["gives_verdict"]) == \
        (4, 1, 3, False)

    pending = [i["id"] for i in client.get(f"{API}/admin/reference-photos?approval_status=pending",
                                           headers=admin).json()["data"]["items"]]
    client.post(f"{API}/admin/reference-photos/decision", headers=admin,
                json={"decision": "approve", "ids": pending})
    item = client.get(f"{API}/admin/reference-photos/coverage", headers=admin).json()["data"]["items"][0]
    assert item["gives_verdict"] is True and item["modern_sources"] == 2
    assert session.scalar(select(AuditEvent).where(AuditEvent.action == "reference_photos.approved"))
    assert client.post(f"{API}/admin/reference-photos/decision", headers=admin,
                       json={"decision": "reject"}).status_code == 422
