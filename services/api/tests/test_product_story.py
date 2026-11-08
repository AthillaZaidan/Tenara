"""Listing story: seller claim + scan + approved catalog chunks, written by a writer and checked by a critic."""
import json

import pytest
from sqlalchemy import select
from test_ai import OBS, FakeVLM, _analyze, _fabric_png, ai, seller  # noqa: F401  (shared scan fixtures)
from test_customization import entry, make_listing  # noqa: F401

from app.main import app
from app.ml.text.story_gen import get_story_llm
from app.models import GalleryEntry, ProductStory
from app.services import gallery as gallery_svc

API = "/api/v1"
KUDA = "Kuda melambangkan keberanian, kekuatan, dan status sosial dalam tradisi Sumba."
UDANG = "Udang melambangkan kehidupan dan kelahiran kembali karena berganti kulit."
MERAH = "Warna merah kombu dahulu menjadi penanda status bangsawan di Sumba Timur."


class FakeTextLLM:
    """Scripted writer and critic replies; records each call."""

    name = "fake-luna"

    def __init__(self, writer=(), critic=()):
        self.writer, self.critic, self.calls = list(writer), list(critic), []

    def complete(self, system, user):
        role = "writer" if "PENULIS" in system else "critic"
        self.calls.append((role, json.loads(user)))
        reply = (self.writer if role == "writer" else self.critic).pop(0)
        return reply if isinstance(reply, str) else json.dumps(reply)


@pytest.fixture
def chunks(session, seller, embedder, make_user):
    """Approved catalog chunks for the listing's entry, plus one from a source nobody approved."""
    _user, listing = seller
    entry_ = session.get(GalleryEntry, listing.entry_id)
    admin = make_user("katalog@example.com", roles=(("admin", "active"),))
    approved = gallery_svc.create_source(session, admin, title="Dossier Sumba", url="https://museum.example/sumba")
    gallery_svc.decide_source(session, admin, approved, "approve", None)
    pending = gallery_svc.create_source(session, admin, title="Blog belum ditinjau")
    ids = {}
    for key, text in (("kuda", KUDA), ("udang", UDANG), ("merah", MERAH)):
        ids[key] = str(gallery_svc.add_chunk(session, approved, text=text, entry_id=entry_.id, embedder=embedder,
                                             meta={"sources": [{"url": f"https://museum.example/{key}"}]}).id)
    ids["pending"] = str(gallery_svc.add_chunk(session, pending, text="Kuda ditenun sejak tahun 1200 oleh Raja X.",
                                               entry_id=entry_.id, embedder=embedder).id)
    session.flush()
    return ids


def _scan(client, auth_header, user, listing, observation=None):
    r = _analyze(client, auth_header(user), listing, FakeVLM(observation=observation))
    assert r.status_code == 200, r.text


def _draft(client, headers, listing, llm):
    app.dependency_overrides[get_story_llm] = lambda: llm
    return client.post(f"{API}/listings/{listing.id}/story", headers=headers)


def _ok(index_count):
    return {"verdicts": [{"index": i, "supported": True, "reason": "ok"} for i in range(index_count)]}


def test_story_needs_a_scan_and_a_technique_that_is_not_in_dispute(client, session, seller, auth_header, chunks):
    user, listing = seller
    r = _draft(client, auth_header(user), listing, FakeTextLLM())
    assert r.status_code == 422 and r.json()["error"]["field"] == "scan"
    _scan(client, auth_header, user, listing, {**OBS, "technique": "songket"})  # claim is ikat
    r = _draft(client, auth_header(user), listing, FakeTextLLM())
    assert r.status_code == 422 and "kurator" in r.json()["error"]["message"]


def test_story_is_claim_plus_scan_plus_cited_culture_and_seller_publishes_it(
        client, session, seller, auth_header, chunks):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    llm = FakeTextLLM(writer=[{"claims": [{"text": KUDA, "chunk_ids": [chunks["kuda"]]},
                                          {"text": UDANG, "chunk_ids": [chunks["udang"]]}]}],
                      critic=[_ok(2)])
    r = _draft(client, auth_header(user), listing, llm)
    assert r.status_code == 201, r.text
    story = r.json()["data"]
    assert [c[0] for c in llm.calls] == ["writer", "critic"]  # no revision needed: two calls
    first, culture = story["body"].split("\n\n")
    assert first.startswith("Menurut penjual, kain ini Tenun Ikat Sumba.")
    assert "Dari foto terlihat tenun ikat dengan motif kuda, udang dalam warna merah, biru, krem." in first
    assert culture == f"{KUDA} {UDANG}"
    assert [c["urls"] for c in story["citations"]] == [["https://museum.example/kuda"], ["https://museum.example/udang"]]
    assert story["status"] == "draft" and story["notes"] == []
    # only approved chunks reached the writer, and the claim and the scan were given as data
    writer_input = llm.calls[0][1]
    assert chunks["pending"] not in {c["id"] for c in writer_input["potongan_sumber"]}
    assert writer_input["tradisi_diklaim"] == "Tenun Ikat Sumba" and writer_input["motif_terlihat"] == ["kuda", "udang"]

    public = client.get(f"{API}/listings/{listing.id}").json()["data"]
    assert public["story"] is None  # nothing public until the seller publishes
    assert client.post(f"{API}/listings/{listing.id}/story/{story['id']}/publish",
                       headers=auth_header(user)).status_code == 200
    public = client.get(f"{API}/listings/{listing.id}").json()["data"]
    assert public["story"]["body"] == story["body"]

    again = _draft(client, auth_header(user), listing, FakeTextLLM(
        writer=[{"claims": [{"text": KUDA, "chunk_ids": [chunks["kuda"]]}]}], critic=[_ok(1)])).json()["data"]
    client.post(f"{API}/listings/{listing.id}/story/{again['id']}/publish", headers=auth_header(user))
    statuses = sorted(s.status for s in session.scalars(select(ProductStory)))
    assert statuses == ["published", "superseded"]
    mine = client.get(f"{API}/listings/{listing.id}/story", headers=auth_header(user)).json()["data"]
    assert mine["published"]["id"] == again["id"] and mine["draft"] is None


@pytest.mark.parametrize(("sentence", "why"), [
    ("Kain ini asli dan dijamin kualitasnya.", "kata terlarang"),
    ("Kuda ditenun sejak tahun 1200 dalam tradisi Sumba.", "angka"),
    ("Kuda dihormati oleh Raja Umbu dalam tradisi Sumba.", "nama"),
    ("Kuda dan udang selalu muncul bersama.", "motif"),  # cites the kuda chunk only: 'udang' is not in it
])
def test_code_gates_drop_unsupported_sentences_before_the_critic(client, session, seller, auth_header, chunks,
                                                                sentence, why):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    llm = FakeTextLLM(writer=[{"claims": [{"text": KUDA, "chunk_ids": [chunks["kuda"]]},
                                          {"text": sentence, "chunk_ids": [chunks["kuda"]]}]}],
                      critic=[_ok(1)])
    story = _draft(client, auth_header(user), listing, llm).json()["data"]
    assert sentence not in story["body"] and KUDA in story["body"]
    assert len(llm.calls[1][1]) == 1  # the critic only saw the sentence that passed the gates
    assert story["notes"] and "dibuang" in story["notes"][0]


def test_invented_or_pending_source_ids_are_dropped(client, session, seller, auth_header, chunks):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    llm = FakeTextLLM(writer=[{"claims": [{"text": KUDA, "chunk_ids": ["k99"]},
                                          {"text": "Kuda ditenun sejak tahun 1200 oleh Raja X.",
                                           "chunk_ids": [chunks["pending"]]}]}])
    story = _draft(client, auth_header(user), listing, llm).json()["data"]
    assert "\n\n" not in story["body"] and [c[0] for c in llm.calls] == ["writer"]
    assert any("Tidak ada kalimat budaya" in n for n in story["notes"])


def test_critic_rejection_gets_one_revision_then_whatever_still_fails_is_dropped(
        client, session, seller, auth_header, chunks):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    overreach = "Kuda adalah lambang utama seluruh kebudayaan Sumba."
    llm = FakeTextLLM(
        writer=[{"claims": [{"text": KUDA, "chunk_ids": [chunks["kuda"]]},
                            {"text": overreach, "chunk_ids": [chunks["kuda"]]}]},
                {"claims": [{"text": KUDA, "chunk_ids": [chunks["kuda"]]},
                            {"text": MERAH, "chunk_ids": [chunks["merah"]]},
                            {"text": "Kuda adalah lambang terpenting di Sumba.", "chunk_ids": [chunks["kuda"]]}]}],
        critic=[{"verdicts": [{"index": 0, "supported": True}, {"index": 1, "supported": False, "reason": "generalisasi"}]},
                {"verdicts": [{"index": 0, "supported": True}, {"index": 1, "supported": True},
                              {"index": 2, "supported": False, "reason": "tidak di sumber"}]}])
    story = _draft(client, auth_header(user), listing, llm).json()["data"]
    assert [c[0] for c in llm.calls] == ["writer", "critic", "writer", "critic"]  # at most one revision
    assert "generalisasi" in json.dumps(llm.calls[2][1]["perbaiki"])
    assert story["body"].endswith(f"{KUDA} {MERAH}") and "terpenting" not in story["body"]


def test_a_missing_critic_verdict_counts_as_unsupported(client, session, seller, auth_header, chunks):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    claims = {"claims": [{"text": KUDA, "chunk_ids": [chunks["kuda"]]}]}
    llm = FakeTextLLM(writer=[claims, claims], critic=[{"verdicts": []}, {"verdicts": [{"index": 0}]}])
    story = _draft(client, auth_header(user), listing, llm).json()["data"]
    assert KUDA not in story["body"]


def test_no_approved_sources_means_no_culture_part_and_no_model_call(client, session, make_partner, make_listing,
                                                                    ai, auth_header):
    from app.models import ListingImage
    from app.services.files import create_file

    user, profile = make_partner("merchant", shop="Toko Tanpa Sumber")
    listing = make_listing()
    listing.merchant_id = profile.id
    session.get(GalleryEntry, listing.entry_id).technique = "Tenun ikat"
    f = create_file(session, ai, owner_id=user.id, kind="listing_photo", data=_fabric_png(),
                    content_type="image/png", visibility="public")
    session.add(ListingImage(listing_id=listing.id, file_id=f.id))
    session.flush()
    _scan(client, auth_header, user, listing)
    story = _draft(client, auth_header(user), listing, None).json()["data"]  # no model configured: still fine
    assert "\n\n" not in story["body"] and story["citations"] == [] and story["model"] == "tanpa-model"


def test_provider_problems_are_503_and_only_the_owner_can_draft(client, session, seller, auth_header, chunks,
                                                               make_partner):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    assert _draft(client, auth_header(user), listing, FakeTextLLM(writer=["bukan json"])).status_code == 503
    assert _draft(client, auth_header(user), listing, None).status_code == 503
    other, _ = make_partner("merchant", shop="Toko Lain")
    assert _draft(client, auth_header(other), listing, FakeTextLLM()).status_code == 404
