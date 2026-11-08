import json

import pytest
from sqlalchemy import func, select

from app.models import CulturalSource, GalleryEntry, SourceChunk
from app.services import gallery as g
from scripts.seed_catalog import CATALOG, approve_catalog, dossier_title, load_catalog, validate

MINI = {"researched_at": "2026-11-08", "traditions": [
    {"name": "Tenun Uji Satu", "province": "Provinsi A", "region": "Kab. A", "community": "A", "technique": "ikat",
     "visual": "Motif kuda merah di atas dasar gelap.", "culture": "Dipakai saat upacara.",
     "distinguish": "Figur kuda besar membedakannya dari ikat geometris.",
     "uncertain": ["Jumlah motif belum pasti."],
     "sources": [{"url": "https://a.example/1", "title": "A1", "publisher": "Museum A"},
                 {"url": "https://b.example/2", "title": "B2", "publisher": "Kampus B"}]},
    {"name": "Songket Uji Dua", "province": "Provinsi B", "technique": "songket",
     "visual": "Benang emas penuh.", "culture": "Kain kebesaran.", "sources": [{"url": "https://c.example/3"}]},
]}


def test_the_researched_catalog_file_is_valid():
    traditions = validate(json.loads(CATALOG.read_text()))
    assert len(traditions) >= 30
    assert len({t["province"] for t in traditions}) >= 20
    assert all(len(t["sources"]) >= 1 for t in traditions)


@pytest.mark.parametrize("bad", [
    {"name": "X", "province": "P", "technique": "batik", "visual": "v", "culture": "c", "sources": [{"url": "https://x"}]},
    {"name": "X", "province": "P", "technique": "ikat", "visual": "v", "culture": "c", "sources": [{"url": "ftp://x"}]},
    {"name": "X", "province": "P", "technique": "ikat", "visual": "", "culture": "c", "sources": [{"url": "https://x"}]},
])
def test_invalid_catalog_entries_are_refused(bad):
    with pytest.raises(ValueError):
        validate({"traditions": [bad]})


def test_load_creates_pending_dossiers_and_two_aspect_chunks(session, embedder):
    out = load_catalog(session, embedder, MINI)
    assert out == {"traditions": 2, "entries_created": 2, "entries_reused": 0, "chunks": 4, "provinces": 2}
    src = session.scalar(select(CulturalSource).where(CulturalSource.title == dossier_title("Tenun Uji Satu")))
    assert src.approval_status == "pending"  # the AI researcher never approves its own research
    assert "https://b.example/2" in src.rights_notes and src.url == "https://a.example/1"
    chunks = list(session.scalars(select(SourceChunk).where(SourceChunk.source_id == src.id)))
    by_aspect = {c.meta["aspect"]: c for c in chunks}
    assert set(by_aspect) == {"visual", "budaya"}
    assert by_aspect["visual"].text.startswith("Tenun Uji Satu (Provinsi A; Kab. A). Tenun ikat. Ciri visual:")
    assert "Belum pasti: Jumlah motif belum pasti." in by_aspect["budaya"].text
    assert by_aspect["visual"].text.endswith("Pembeda: Figur kuda besar membedakannya dari ikat geometris.")
    meta = by_aspect["visual"].meta
    assert meta["technique"] == "ikat" and meta["embed_model"] == embedder.name and len(meta["sources"]) == 2
    assert all(c.embedding is not None for c in chunks)
    entry = session.get(GalleryEntry, chunks[0].entry_id)
    assert entry.name == "Tenun Uji Satu" and entry.status == "draft"


def test_existing_entries_are_reused_and_reloading_does_not_duplicate(session, embedder, make_user):
    admin = make_user("admin@example.com", roles=(("admin", "active"),))
    g.create_entry(session, admin, name="Tenun Uji Satu")
    first = load_catalog(session, embedder, MINI)
    assert first["entries_reused"] == 1 and first["entries_created"] == 1
    load_catalog(session, embedder, MINI)
    assert session.scalar(select(func.count()).select_from(GalleryEntry).where(GalleryEntry.name == "Tenun Uji Satu")) == 1
    assert session.scalar(select(func.count()).select_from(CulturalSource)) == 2
    assert session.scalar(select(func.count()).select_from(SourceChunk)) == 4


def test_only_an_active_admin_can_approve(session, embedder, make_user):
    load_catalog(session, embedder, MINI)
    make_user("buyer@example.com")
    with pytest.raises(SystemExit):
        approve_catalog(session, "buyer@example.com", MINI)
    make_user("curator@example.com", roles=(("admin", "active"),))
    assert approve_catalog(session, "curator@example.com", MINI) == 2
    assert {s.approval_status for s in session.scalars(select(CulturalSource))} == {"approved"}
    assert approve_catalog(session, "curator@example.com", MINI) == 0  # already approved
