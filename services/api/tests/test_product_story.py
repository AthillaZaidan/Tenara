"""Listing story: seller claim + scan + approved catalog chunks, written in the background by a writer
and checked by a critic."""
import json

import pytest
from sqlalchemy import select
from test_ai import OBS, FakeVLM, _analyze, _fabric_png, ai, seller  # noqa: F401  (shared scan fixtures)
from test_customization import entry, make_listing  # noqa: F401

from app.ml.text import product_story
from app.models import GalleryEntry, Job, ProductStory
from app.services import gallery as gallery_svc
from app.services import jobs
from app.workers import handlers

API = "/api/v1"
KUDA = "Kuda melambangkan keberanian, kekuatan, dan status sosial dalam tradisi Sumba."
UDANG = "Udang melambangkan kehidupan dan kelahiran kembali karena berganti kulit."
MERAH = "Warna merah kombu dahulu menjadi penanda status bangsawan di Sumba Timur."
LOOK = "Pada kain ini, merah, biru, dan krem berdiri di atas dasar gelap seperti nyala yang tertahan."
CLOSE = "Pada kain ini, kuda dan udang kembali bertemu dalam irama warna yang tenang."


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


@pytest.fixture
def run_story(client, session, monkeypatch, embedder):
    """Queue the story through the API, run the worker once, and return (queue response, draft or None)."""
    def _run(headers, listing, llm):
        monkeypatch.setattr(handlers, "_story_llm", lambda: llm)
        monkeypatch.setattr(handlers, "_embedder", lambda: embedder)
        queued = client.post(f"{API}/listings/{listing.id}/story", headers=headers)
        if queued.status_code == 202:
            while jobs.process_one(session):
                pass
        mine = client.get(f"{API}/listings/{listing.id}/story", headers=headers).json()["data"]
        return queued, mine
    return _run


def _scan(client, auth_header, user, listing, observation=None):
    r = _analyze(client, auth_header(user), listing, FakeVLM(observation=observation))
    assert r.status_code == 200, r.text


def _ok(index_count):
    return {"verdicts": [{"index": i, "supported": True, "reason": "ok"} for i in range(index_count)]}


def _c(paragraph, text, *ids):
    return {"paragraph": paragraph, "text": text, "chunk_ids": list(ids)}


def test_story_needs_a_scan_and_a_technique_that_is_not_in_dispute(client, session, seller, auth_header, chunks,
                                                                  run_story):
    user, listing = seller
    queued, _ = run_story(auth_header(user), listing, FakeTextLLM())
    assert queued.status_code == 422 and queued.json()["error"]["field"] == "scan"
    _scan(client, auth_header, user, listing, {**OBS, "technique": "songket"})  # the claim is ikat
    queued, _ = run_story(auth_header(user), listing, FakeTextLLM())
    assert queued.status_code == 422 and "kurator" in queued.json()["error"]["message"]
    assert session.scalar(select(Job).where(Job.kind == "story.generate")) is None  # nothing was queued


def test_story_is_written_in_the_background_in_three_paragraphs_and_the_seller_publishes_it(
        client, session, seller, auth_header, chunks, run_story):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    llm = FakeTextLLM(writer=[{"claims": [_c(1, LOOK, "foto"), _c(3, KUDA, chunks["kuda"]),
                                          _c(3, UDANG, chunks["udang"]), _c(2, MERAH, chunks["merah"]),
                                          _c(3, CLOSE, "foto")]}],
                      critic=[_ok(5)])
    queued, mine = run_story(auth_header(user), listing, llm)
    assert queued.status_code == 202 and queued.json()["data"]["job"]["status"] == "queued"
    assert mine["job"]["status"] == "completed"
    story = mine["draft"]
    assert [c[0] for c in llm.calls] == ["writer", "critic"]  # nothing rejected: no revision
    claim, look, place, meaning = story["body"].split("\n\n")
    assert claim == "Menurut penjual, kain ini Tenun Ikat Sumba."
    assert look == LOOK and place == MERAH and meaning == f"{KUDA} {UDANG} {CLOSE}"
    assert story["sentences"][0] == {"paragraph": 1, "text": LOOK, "sources": ["foto"]}
    assert [c["urls"] for c in story["citations"]] == [["https://museum.example/kuda"], ["https://museum.example/udang"],
                                                       ["https://museum.example/merah"]]
    # the writer got only approved chunks, and the photo observation as its own text
    writer_input = llm.calls[0][1]
    assert chunks["pending"] not in {c["id"] for c in writer_input["teks_katalog"]}
    assert writer_input["pengamatan_foto"].startswith("Pengamatan foto: teknik tenun ikat; motif kuda, udang")
    # the critic judged the 'foto' sentences against that observation
    assert llm.calls[1][1][0]["teks_dikutip"][0].startswith("Pengamatan foto:")

    assert client.get(f"{API}/listings/{listing.id}").json()["data"]["story"] is None  # private until published
    assert client.post(f"{API}/listings/{listing.id}/story/{story['id']}/publish",
                       headers=auth_header(user)).status_code == 200
    public = client.get(f"{API}/listings/{listing.id}").json()["data"]["story"]
    assert public["body"] == story["body"] and public["sentences"] == story["sentences"]
    assert public["reference_photos"] == []  # none approved and displayable for this entry yet


def test_a_second_request_while_one_is_queued_reuses_the_job(client, session, seller, auth_header, chunks):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    first = client.post(f"{API}/listings/{listing.id}/story", headers=auth_header(user)).json()["data"]["job"]
    second = client.post(f"{API}/listings/{listing.id}/story", headers=auth_header(user)).json()["data"]["job"]
    assert first["id"] == second["id"]


def test_a_photo_sentence_cannot_carry_a_motif_or_name_the_scan_did_not_see(client, session, seller, auth_header,
                                                                          chunks, run_story):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    llm = FakeTextLLM(writer=[{"claims": [_c(1, "Pada kain ini, naga Majapahit melingkar di tepi.", "foto"),
                                          _c(3, KUDA, chunks["kuda"])]}], critic=[_ok(1)])
    _, mine = run_story(auth_header(user), listing, llm)
    assert "naga" not in mine["draft"]["body"] and KUDA in mine["draft"]["body"]


@pytest.mark.parametrize(("sentence", "why"), [
    ("Kain ini asli dan dijamin kualitasnya.", "kata terlarang"),
    ("Kuda ditenun sejak tahun 1200 dalam tradisi Sumba.", "angka"),
    ("Kuda dihormati oleh Raja Umbu dalam tradisi Sumba.", "nama"),
    ("Kuda dan udang selalu muncul bersama.", "motif"),  # cites the kuda chunk only: 'udang' is not in it
])
def test_code_gates_drop_unsupported_sentences_before_the_critic(client, session, seller, auth_header, chunks,
                                                                run_story, sentence, why):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    llm = FakeTextLLM(writer=[{"claims": [_c(3, KUDA, chunks["kuda"]), _c(3, sentence, chunks["kuda"])]}],
                      critic=[_ok(1)])
    _, mine = run_story(auth_header(user), listing, llm)
    story = mine["draft"]
    assert sentence not in story["body"] and KUDA in story["body"]
    assert len(llm.calls[1][1]) == 1  # the critic only saw the sentence that passed the gates
    assert story["notes"] and "dibuang" in story["notes"][0]


def test_ids_copied_into_the_sentence_are_removed_not_mistaken_for_numbers(client, session, seller, auth_header,
                                                                         chunks, run_story):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    cid = chunks["kuda"]
    llm = FakeTextLLM(writer=[{"claims": [_c(3, f"{KUDA[:-1]} [{cid}].", cid)]}], critic=[_ok(1)])
    _, mine = run_story(auth_header(user), listing, llm)
    assert mine["draft"]["body"].endswith(KUDA) and cid not in mine["draft"]["body"]


def test_invented_or_pending_source_ids_are_dropped(client, session, seller, auth_header, chunks, run_story):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    llm = FakeTextLLM(writer=[{"claims": [_c(3, KUDA, "k99"),
                                          _c(3, "Kuda ditenun sejak tahun 1200 oleh Raja X.", chunks["pending"])]}])
    _, mine = run_story(auth_header(user), listing, llm)
    story = mine["draft"]
    assert story["body"].startswith("Menurut penjual") and "Dari foto terlihat" in story["body"]  # plain fallback
    assert [c[0] for c in llm.calls] == ["writer"] and story["sentences"] == []
    assert any("Tidak ada kalimat budaya" in n for n in story["notes"])


def test_only_photo_sentences_are_not_a_story(client, session, seller, auth_header, chunks, run_story):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    llm = FakeTextLLM(writer=[{"claims": [_c(1, LOOK, "foto")]}], critic=[_ok(1)])
    _, mine = run_story(auth_header(user), listing, llm)
    assert mine["draft"]["sentences"] == [] and any("budaya" in n for n in mine["draft"]["notes"])


def test_critic_rejection_gets_one_revision_then_whatever_still_fails_is_dropped(
        client, session, seller, auth_header, chunks, run_story):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    overreach = "Kuda adalah lambang utama seluruh kebudayaan Sumba."
    llm = FakeTextLLM(
        writer=[{"claims": [_c(3, KUDA, chunks["kuda"]), _c(3, overreach, chunks["kuda"])]},
                {"claims": [_c(3, KUDA, chunks["kuda"]), _c(2, MERAH, chunks["merah"]),
                            _c(3, "Kuda adalah lambang terpenting di Sumba.", chunks["kuda"])]}],
        critic=[{"verdicts": [{"index": 0, "supported": True}, {"index": 1, "supported": False, "reason": "generalisasi"}]},
                {"verdicts": [{"index": 0, "supported": True}, {"index": 1, "supported": True},
                              {"index": 2, "supported": False, "reason": "tidak di sumber"}]}])
    _, mine = run_story(auth_header(user), listing, llm)
    assert [c[0] for c in llm.calls] == ["writer", "critic", "writer", "critic"]  # at most one revision
    assert "generalisasi" in json.dumps(llm.calls[2][1]["perbaiki"])
    body = mine["draft"]["body"]
    assert MERAH in body and KUDA in body and "terpenting" not in body


def test_a_missing_critic_verdict_counts_as_unsupported(client, session, seller, auth_header, chunks, run_story):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    claims = {"claims": [_c(3, KUDA, chunks["kuda"])]}
    llm = FakeTextLLM(writer=[claims, claims], critic=[{"verdicts": []}, {"verdicts": [{"index": 0}]}])
    _, mine = run_story(auth_header(user), listing, llm)
    assert KUDA not in mine["draft"]["body"]


def test_no_approved_sources_means_no_culture_part_and_no_model_call(client, session, make_partner, make_listing,
                                                                    ai, auth_header, run_story):
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
    _, mine = run_story(auth_header(user), listing, None)  # no model configured: still a plain draft
    story = mine["draft"]
    assert "\n\n" not in story["body"] and story["citations"] == [] and story["model"] == "tanpa-model"


def test_provider_failures_retry_then_fail_honestly(client, session, seller, auth_header, chunks, run_story):
    user, listing = seller
    _scan(client, auth_header, user, listing)
    _, mine = run_story(auth_header(user), listing, FakeTextLLM(writer=["bukan json"]))
    assert mine["job"]["status"] == "queued" and mine["draft"] is None  # retried later by the queue
    job = session.get(Job, mine["job"]["id"])
    job.attempts = jobs.MAX_ATTEMPTS
    job.status = "processing"
    jobs.run_job(session, job)
    assert job.status == "failed" and mine["draft"] is None
    queued, _ = run_story(auth_header(user), listing, None)
    retry = session.get(Job, queued.json()["data"]["job"]["id"])
    assert retry.status == "failed" and "dikonfigurasi" in retry.error  # not configured: no pointless retries


def test_only_the_owner_can_queue_read_or_publish(client, session, seller, auth_header, chunks, make_partner):
    user, listing = seller
    other, _ = make_partner("merchant", shop="Toko Lain")
    assert client.post(f"{API}/listings/{listing.id}/story", headers=auth_header(other)).status_code == 404
    assert client.get(f"{API}/listings/{listing.id}/story", headers=auth_header(other)).status_code == 404
    draft = ProductStory(listing_id=listing.id, body="x", model="m", created_by=user.id)
    session.add(draft)
    session.flush()
    url = f"{API}/listings/{listing.id}/story/{draft.id}/publish"
    assert client.post(url, headers=auth_header(other)).status_code == 404
    assert client.post(url, headers=auth_header(user)).status_code == 200
    assert client.post(url, headers=auth_header(user)).status_code == 422  # only a draft can be published


def test_published_story_shows_curated_reference_photos_of_the_claimed_tradition(
        client, session, seller, auth_header, chunks, run_story, storage):
    from app.ml.vision import photo_match
    from app.ml.vision.photo_match import FakePhotoEmbedder
    from app.services.files import create_file

    user, listing = seller
    entry_ = session.get(GalleryEntry, listing.entry_id)
    for allowed in (True, False):
        f = create_file(session, storage, owner_id=user.id, kind="reference_photo", data=_fabric_png(),
                        content_type="image/png", visibility="public")
        ref = photo_match.add_reference(session, FakePhotoEmbedder(), entry=entry_, image=_fabric_png(),
                                        style="archival", source_label="museum", file_id=f.id,
                                        credit=f"Museum {allowed}", license="CC0", display_allowed=allowed)
        ref.approval_status = "approved"
    session.flush()
    _scan(client, auth_header, user, listing)
    llm = FakeTextLLM(writer=[{"claims": [_c(3, KUDA, chunks["kuda"])]}], critic=[_ok(1)])
    _, mine = run_story(auth_header(user), listing, llm)
    client.post(f"{API}/listings/{listing.id}/story/{mine['draft']['id']}/publish", headers=auth_header(user))
    photos = client.get(f"{API}/listings/{listing.id}").json()["data"]["story"]["reference_photos"]
    assert [p["credit"] for p in photos] == ["Museum True"] and photos[0]["url"].startswith("/api/v1/files/")


def test_writer_and_critic_prompts_keep_the_safety_rules():
    w, c = product_story.WRITER_SYSTEM, product_story.CRITIC_SYSTEM
    assert "DATA TIDAK" in w and "Belum pasti" in w and "asli" in w and "'foto'" in w
    assert "Metafora" in c and "Tolak HANYA" in c and "Belum pasti" in c
