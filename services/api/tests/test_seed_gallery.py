import csv
import json

import pytest
from sqlalchemy import select

from app.models import AuditEvent, CulturalSource, GalleryEntry, SourceChunk, Story
from app.services import gallery as svc
from scripts.seed_gallery import seed_gallery

MEANING = "Fauna dalam tradisi Sumba berkaitan dengan kekuatan, status, dan keberanian."


@pytest.fixture
def data_dir(tmp_path):
    ntt = tmp_path / "mendeley_ntt_534"
    ntt.mkdir()
    (ntt / "534 NTT motifs.json").write_text(json.dumps([
        {"file_original": "a.jpg", "jenis": "Tenun", "motif_name": "Fauna; kuda",
         "category": ["Fauna"], "provinsi": "NTT", "kabupaten_kota": "Sumba Timur",
         "philosophical_meaning": MEANING, "technique": "Tenun ikat lungsi"},
        {"file_original": "b.jpg", "jenis": "Tenun", "motif_name": "Geometris",
         "category": ["Geometris"], "provinsi": "NTT", "kabupaten_kota": "Flores",
         "philosophical_meaning": "Pola geometris melambangkan keteraturan hidup masyarakat.",
         "technique": "Tenun Ikat"},
    ]))
    bali = tmp_path / "mendeley_bali_336"
    bali.mkdir()
    (bali / "336 bali motifs.json").write_text(json.dumps([
        {"file_original": "c.jpg", "jenis": "Tenun Songket Bali (Tenun dengan benang emas)",
         "motif_name": "Dekoratif", "category": ["Flora"], "provinsi": "Bali",
         "kabupaten_kota": "Klungkung",
         "philosophical_meaning": "Tidak terdapat pemaknaan khusus, hanya merepresentasikan identitas.",
         "technique": "Tenun"},
    ]))
    endek = tmp_path / "mendeley_endek_multimodal"
    endek.mkdir()
    with (endek / "semantic_annotations-4.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["image_id", "motif_name", "motif_status", "category",
                                           "description_id", "symbolic_meaning"])
        w.writeheader()
        w.writerow({"image_id": 1, "motif_name": "Rangrang", "motif_status": "Verified",
                    "category": "Geometric", "description_id": "Motif geometris berulang.",
                    "symbolic_meaning": "Melambangkan keseimbangan dan keteraturan dalam hidup."})
        w.writerow({"image_id": 2, "motif_name": "Tak dikenal", "motif_status": "Unknown",
                    "category": "", "description_id": "", "symbolic_meaning": ""})
    return tmp_path


def test_seed_creates_grouped_entries_in_review(session, data_dir, embedder):
    summary = seed_gallery(session, data_dir, embedder=embedder)
    assert summary == {"created": 4, "skipped": 0, "published": 0}
    names = {e.name for e in session.scalars(select(GalleryEntry))}
    assert names == {"Tenun Ikat Sumba", "Tenun Ikat Flores", "Songket Bali", "Endek Bali"}
    sumba = session.scalar(select(GalleryEntry).where(GalleryEntry.name == "Tenun Ikat Sumba"))
    assert sumba.status == "draft"
    assert sumba.technique == "Tenun ikat lungsi"
    story = session.scalar(select(Story).where(Story.entry_id == sumba.id))
    assert story.status == "in_review"
    assert MEANING in story.body
    assert len(story.unresolved) == 2


def test_seed_cites_real_chunks_and_sources(session, data_dir, embedder):
    seed_gallery(session, data_dir, embedder=embedder)
    source = session.scalar(select(CulturalSource).where(CulturalSource.title.like("534 East%")))
    assert source.license == "CC BY 4.0" and source.approval_status == "pending"
    assert session.scalars(select(SourceChunk).where(SourceChunk.source_id == source.id)).first().embedding is not None


def test_unknown_status_rows_are_excluded(session, data_dir, embedder):
    seed_gallery(session, data_dir, embedder=embedder)
    texts = [c.text for c in session.scalars(select(SourceChunk))]
    assert not any("Tak dikenal" in t for t in texts)


def test_seed_is_idempotent(session, data_dir, embedder):
    seed_gallery(session, data_dir, embedder=embedder)
    again = seed_gallery(session, data_dir, embedder=embedder)
    assert again == {"created": 0, "skipped": 4, "published": 0}


def test_publish_demo_marks_seed_and_is_searchable(session, data_dir, embedder):
    summary = seed_gallery(session, data_dir, embedder=embedder, publish_demo=True)
    assert summary["published"] == 4
    entries = list(session.scalars(select(GalleryEntry)))
    assert all(e.status == "published" and e.is_demo_seed for e in entries)
    actions = {e.action for e in session.scalars(select(AuditEvent))}
    assert "gallery.demo_seeded" in actions
    result = svc.search(session, embedder, "songket")
    assert result["results"][0]["entry"]["name"] == "Songket Bali"
    p = svc.passport(session, entries[0])
    assert p["review"]["is_demo_seed"] is True and p["citations"]
