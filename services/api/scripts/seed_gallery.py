"""Seed Gallery entries from the Mendeley tenun metadata datasets (CC BY 4.0).

Usage (from services/api):
    uv run python -m scripts.seed_gallery                 # draft/in_review entries for a curator
    uv run python -m scripts.seed_gallery --publish-demo  # also approve + publish as labelled demo seed

Each dataset record becomes a cited source chunk; entries are grouped per tradition. Stories are
deterministic extracts of the dataset text (no invented claims) and list what stays unresolved.
"""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models import GalleryEntry
from app.services import gallery as svc
from app.services.embedding import Embedder, get_embedder

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA = ROOT / "data" / "tenun_datasets"
LICENSE = "CC BY 4.0"
PUBLISHER = "Universitas Negeri Gorontalo (Mendeley Data)"
UNRESOLVED = [
    "Asal-usul historis motif belum diverifikasi kurator",
    "Pemaknaan pada dataset bersifat umum dan perlu dikonfirmasi komunitas pemilik tradisi",
]

SOURCES = {
    "ntt": ("534 East Nusa Tenggara Traditional Textile Motif Image Dataset",
            "https://doi.org/10.17632/wj3r25d8jv.1"),
    "bali": ("336 Bali Traditional Textile Motif Image Dataset",
             "https://doi.org/10.17632/nc54kz78wp.1"),
    "endek": ("Endek Multimodal Dataset V1", "https://doi.org/10.17632/52ffyj9x3c.1"),
}


def _first(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return " ".join(str(value or "").split())


def _ntt_group(rec: dict) -> tuple[str, str]:
    place = _first(rec.get("kabupaten_kota")).lower()
    tech = _first(rec.get("technique")).lower()
    technique = ("Tenun ikat lungsi" if "lungsi" in tech else
                 "Tenun ikat pahikung" if "pahikung" in tech else "Tenun ikat")
    if "sumba" in place:
        return "Tenun Ikat Sumba", technique
    if "flores" in place or "manggarai" in place:
        return "Tenun Ikat Flores", technique
    return f"Tenun {_first(rec.get('kabupaten_kota')) or 'NTT'}", technique


def _bali_group(rec: dict) -> tuple[str, str, str | None]:
    jenis = _first(rec.get("jenis")).lower()
    place = _first(rec.get("kabupaten_kota"))
    if "songket" in jenis:
        return "Songket Bali", "Songket", None
    if "endek" in jenis:
        return "Endek Bali", "Tenun ikat pakan", None
    if "gringsing" in jenis:
        return "Gringsing Tenganan", "Tenun ikat ganda", "Tenganan"
    if "wali" in jenis:
        return "Tenun Wali/Wewali Bali", "Tenun", place or None
    return "Tenun Bali", "Tenun", place or None


def _record_text(rec: dict) -> str:
    parts = [_first(rec.get("motif_name")), f"Kategori: {_first(rec.get('category'))}",
             f"Makna: {_first(rec.get('philosophical_meaning'))}",
             f"Lokasi: {_first(rec.get('kabupaten_kota'))}"]
    return ". ".join(p for p in parts if not p.endswith(": "))


def collect_groups(data_dir: Path) -> dict[str, dict]:
    """Return {entry name: {meta..., 'records': [{'dataset', 'text', 'locator', 'category', 'meaning', 'motif'}]}}."""
    groups: dict[str, dict] = {}

    def add(name, dataset, region, technique, textile_type, community, record):
        g = groups.setdefault(name, {"region": region, "techniques": Counter(),
                                     "textile_type": textile_type, "community": community,
                                     "records": []})
        g["techniques"][technique] += 1
        g["records"].append({"dataset": dataset, **record})

    ntt = data_dir / "mendeley_ntt_534" / "534 NTT motifs.json"
    if ntt.exists():
        for rec in json.loads(ntt.read_text()):
            name, technique = _ntt_group(rec)
            add(name, "ntt", "NTT", technique, "Tenun ikat", None,
                {"text": _record_text(rec), "locator": rec.get("file_original"),
                 "category": _first(rec.get("category")), "motif": _first(rec.get("motif_name")),
                 "meaning": _first(rec.get("philosophical_meaning"))})
    bali = data_dir / "mendeley_bali_336" / "336 bali motifs.json"
    if bali.exists():
        for rec in json.loads(bali.read_text()):
            name, technique, community = _bali_group(rec)
            add(name, "bali", "Bali", technique, name.split(" Bali")[0], community,
                {"text": _record_text(rec), "locator": rec.get("file_original"),
                 "category": _first(rec.get("category")), "motif": _first(rec.get("motif_name")),
                 "meaning": _first(rec.get("philosophical_meaning"))})
    endek = data_dir / "mendeley_endek_multimodal" / "semantic_annotations-4.csv"
    if endek.exists():
        with endek.open(encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                if (row.get("motif_status") or "").strip().lower() == "unknown":
                    continue
                meaning = " ".join((row.get("symbolic_meaning") or "").split())
                text = ". ".join(p for p in [
                    row.get("motif_name", ""), f"Kategori: {row.get('category', '')}",
                    f"Makna: {meaning}" if meaning else "",
                    " ".join((row.get("description_id") or "").split())] if p)
                add("Endek Bali", "endek", "Bali", "Tenun ikat pakan", "Endek", None,
                    {"text": text, "locator": f"image_id {row.get('image_id')}",
                     "category": _first(row.get("category")), "motif": row.get("motif_name", ""),
                     "meaning": meaning})
    return groups


def _story_body(name: str, records: list[dict]) -> tuple[str, list[int]]:
    cats = Counter(c.strip() for r in records for c in r["category"].split(",") if c.strip())
    top = ", ".join(c for c, _ in cats.most_common(3)) or "beragam kategori"
    lines = [
        f"Dataset terbuka mendokumentasikan {len(records)} motif untuk {name}, "
        f"terutama berkategori {top}."
    ]
    quoted, seen = [], set()
    for i, r in enumerate(records):
        meaning = r["meaning"]
        if len(meaning) > 30 and meaning not in seen and len(quoted) < 3:
            seen.add(meaning)
            quoted.append(i)
            lines.append(f"Untuk motif \"{r['motif'][:80]}\", dataset mencatat: \"{meaning}\"")
    return "\n".join(lines), quoted


def seed_gallery(session: Session, data_dir: Path, *, embedder: Embedder | None,
                 publish_demo: bool = False) -> dict:
    groups = collect_groups(data_dir)
    summary = {"created": 0, "skipped": 0, "published": 0}
    sources = {}
    for name, g in sorted(groups.items()):
        if session.scalar(select(GalleryEntry.id).where(GalleryEntry.name == name)):
            summary["skipped"] += 1
            continue
        technique = g["techniques"].most_common(1)[0][0]
        entry = svc.create_entry(
            session, None, name=name, kind="tradition", textile_type=g["textile_type"],
            technique=technique, region=g["region"], community=g["community"],
            summary=f"{g['textile_type']} dari {g['region']}; {len(g['records'])} motif "
                    f"terdokumentasi dalam dataset terbuka.",
            is_demo_seed=publish_demo)
        chunks = []
        for rec in g["records"]:
            dataset = rec["dataset"]
            if dataset not in sources:
                title, url = SOURCES[dataset]
                sources[dataset] = svc.create_source(
                    session, None, title=title, publisher=PUBLISHER, url=url, license=LICENSE,
                    rights_notes="Dataset CC BY 4.0; atribusi wajib. Makna bersifat umum.")
            chunks.append(svc.add_chunk(session, sources[dataset], text=rec["text"],
                                        locator=rec["locator"], entry_id=entry.id,
                                        meta={"dataset": dataset}, embedder=embedder))
        body, quoted_idx = _story_body(name, g["records"])
        cite_idx = quoted_idx or [0]
        citations = [{"source_id": chunks[i].source_id, "chunk_id": chunks[i].id,
                      "locator": chunks[i].locator} for i in cite_idx]
        story = svc.create_story(session, None, entry, body=body, citations=citations,
                                 unresolved=UNRESOLVED)
        svc.submit_story(session, None, story)
        summary["created"] += 1
        if publish_demo:
            for source in {c["source_id"] for c in citations}:
                src = next(s for s in sources.values() if s.id == source)
                if src.approval_status != "approved":
                    svc.decide_source(session, None, src, "approve", "demo seed",
                                      action_prefix="gallery.demo_seeded")
            svc.decide_story(session, None, story, "approve", "demo seed", embedder)
            svc.publish_entry(session, None, entry, embedder, action="gallery.demo_seeded")
            summary["published"] += 1
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--publish-demo", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as session:
        result = seed_gallery(session, args.data_dir, embedder=get_embedder(),
                              publish_demo=args.publish_demo)
        session.commit()
    print(result)


if __name__ == "__main__":
    main()
