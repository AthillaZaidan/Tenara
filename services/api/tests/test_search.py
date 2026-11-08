import pytest

from app.services import gallery as svc

API = "/api/v1"


@pytest.fixture
def seeded(session, embedder, make_user):
    """Three published entries created directly through the service layer."""
    admin = make_user("admin@example.com", roles=(("admin", "active"),))
    source = svc.create_source(session, admin, title="Dataset", license="CC BY 4.0")
    svc.decide_source(session, admin, source, "approve", None)
    specs = [
        ("Tenun Ikat Sumba", "NTT", "Tenun ikat",
         "Motif kuda melambangkan keberanian dan status sosial dalam tradisi Sumba."),
        ("Songket Bali", "Bali", "Songket",
         "Songket dengan benang emas dipakai pada upacara adat dan pernikahan di Bali."),
        ("Endek Bali", "Bali", "Tenun ikat pakan",
         "Endek bermotif bunga dipakai sehari-hari dan pada acara keluarga."),
    ]
    for name, region, technique, summary in specs:
        entry = svc.create_entry(session, admin, name=name, region=region, technique=technique,
                                 summary=summary)
        story = svc.create_story(session, admin, entry, body=summary,
                                 citations=[{"source_id": source.id}])
        svc.submit_story(session, admin, story)
        svc.decide_story(session, admin, story, "approve", None, embedder)
        svc.publish_entry(session, admin, entry, embedder)
    session.flush()


def _search(client, **body):
    return client.post(f"{API}/search/semantic", json=body)


def test_keyword_match_with_snippet(client, seeded):
    r = _search(client, query="songket")
    data = r.json()["data"]
    assert r.status_code == 200
    assert data["mode"] == "hybrid"
    assert data["results"][0]["entry"]["name"] == "Songket Bali"
    assert data["results"][0]["match"]["type"] in ("keyword", "hybrid")
    assert "songket" in data["results"][0]["match"]["snippet"].lower()


def test_meaning_based_match(client, seeded, monkeypatch):
    # The fake bag-of-words embedder scores far lower than the real model, so lower the cutoff.
    monkeypatch.setattr("app.services.gallery.settings.search_min_similarity", 0.1)
    data = _search(client, query="simbol keberanian kuda").json()["data"]
    assert data["results"][0]["entry"]["name"] == "Tenun Ikat Sumba"
    assert data["results"][0]["match"]["type"] == "semantic"
    assert data["results"][0]["match"]["similarity"] >= 0.1


def test_no_match_returns_explanation_not_invented_results(client, seeded):
    data = _search(client, query="xylophone quantum").json()["data"]
    assert data["results"] == []
    assert "Tidak ada" in data["explanation"]


def test_source_chunk_match_returns_cited_evidence(client, session, embedder, make_user):
    admin = make_user("admin@example.com", roles=(("admin", "active"),))
    source = svc.create_source(session, admin, title="Buku Motif", license="CC BY 4.0")
    svc.decide_source(session, admin, source, "approve", None)
    entry = svc.create_entry(session, admin, name="Tenun Uji", summary="Kain uji.")
    svc.add_chunk(session, source, entry_id=entry.id, embedder=embedder,
                  text="motif burung merpati melambangkan perdamaian")
    story = svc.create_story(session, admin, entry, body="Kain uji.",
                             citations=[{"source_id": source.id}])
    svc.submit_story(session, admin, story)
    svc.decide_story(session, admin, story, "approve", None, embedder)
    svc.publish_entry(session, admin, entry, embedder)
    hit = _search(client, query="perdamaian merpati").json()["data"]["results"][0]
    assert hit["entry"]["name"] == "Tenun Uji"
    assert hit["match"]["type"] == "semantic"
    assert hit["match"]["evidence"] == {"text": "motif burung merpati melambangkan perdamaian",
                                        "source": "Buku Motif"}


def test_chunks_of_unapproved_sources_are_not_evidence(client, session, embedder, make_user):
    admin = make_user("admin@example.com", roles=(("admin", "active"),))
    approved = svc.create_source(session, admin, title="Disetujui")
    svc.decide_source(session, admin, approved, "approve", None)
    pending = svc.create_source(session, admin, title="Belum disetujui")
    entry = svc.create_entry(session, admin, name="Tenun Uji", summary="Kain uji.")
    svc.add_chunk(session, pending, entry_id=entry.id, embedder=embedder,
                  text="klaim rahasia tentang naga emas")
    story = svc.create_story(session, admin, entry, body="Kain uji.",
                             citations=[{"source_id": approved.id}])
    svc.submit_story(session, admin, story)
    svc.decide_story(session, admin, story, "approve", None, embedder)
    svc.publish_entry(session, admin, entry, embedder)
    assert _search(client, query="naga emas rahasia").json()["data"]["results"] == []


def test_region_filter(client, seeded):
    data = _search(client, query="songket", region="bali").json()["data"]
    assert data["results"] and all(r["entry"]["region"] == "Bali" for r in data["results"])
    assert _search(client, query="songket", region="NTT").json()["data"]["results"] == []


def test_unpublished_entries_are_never_returned(client, session, make_user, seeded):
    admin = make_user("a2@example.com", roles=(("admin", "active"),))
    svc.create_entry(session, admin, name="Rahasia Draft", summary="songket draft rahasia")
    names = [r["entry"]["name"] for r in _search(client, query="rahasia draft").json()["data"]["results"]]
    assert "Rahasia Draft" not in names


def test_keyword_mode_without_embedder(client, session, seeded):
    from app.main import app
    from app.ml.text.embedding import get_embedder

    app.dependency_overrides[get_embedder] = lambda: None
    data = _search(client, query="songket").json()["data"]
    assert data["mode"] == "keyword"
    assert data["results"][0]["entry"]["name"] == "Songket Bali"


def test_blank_query_is_validation_error(client):
    assert _search(client, query="").status_code == 422
