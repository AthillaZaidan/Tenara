"""Load the researched tenun catalog (data/tenun_catalog.json) into the Gallery RAG store.

Per tradition:
  - a Gallery entry (an existing entry with the same name is reused; new ones stay drafts),
  - one "dossier" source listing every web source used (approval stays PENDING),
  - two chunks with embeddings: aspect "visual" (what a camera can see: technique, motifs,
    colours, layout) for matching scans, and aspect "budaya" (meaning, use, community, plus what is
    still uncertain) for the writer.

Idempotent: re-running replaces each dossier's chunks. Approval is a human decision:
    uv run python -m scripts.seed_catalog                          # load; sources stay pending
    uv run python -m scripts.seed_catalog --approve-by admin@x.id  # a curator approves after review
"""
import argparse
import json
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.ml.text.embedding import Embedder, get_embedder
from app.models import CulturalSource, GalleryEntry, RoleAssignment, SourceChunk, User
from app.services import gallery as gallery_svc

CATALOG = Path(__file__).resolve().parents[1] / "data" / "tenun_catalog.json"
TECHNIQUES = {"ikat", "songket", "plain_weave", "other"}
TECHNIQUE_TEXT = {"ikat": "Tenun ikat", "songket": "Songket", "plain_weave": "Tenun polos atau lurik",
                  "other": "Tenun"}
LICENSE = "Tidak diketahui; fakta dirangkum ulang, bukan disalin"


def dossier_title(name: str) -> str:
    return f"Dossier riset web: {name}"


def validate(catalog: dict) -> list[dict]:
    traditions = catalog.get("traditions") or []
    names = set()
    for t in traditions:
        for key in ("name", "province", "technique", "visual", "culture", "sources"):
            if not t.get(key):
                raise ValueError(f"{t.get('name', '?')}: missing {key}")
        if t["technique"] not in TECHNIQUES:
            raise ValueError(f"{t['name']}: unknown technique {t['technique']}")
        if t["name"] in names:
            raise ValueError(f"duplicate tradition {t['name']}")
        names.add(t["name"])
        for s in t["sources"]:
            if not str(s.get("url", "")).startswith(("http://", "https://")):
                raise ValueError(f"{t['name']}: bad source url {s.get('url')}")
    return traditions


def chunk_texts(t: dict) -> dict[str, str]:
    place = "; ".join(p for p in (t["province"], t.get("region")) if p)
    visual = f"{t['name']} ({place}). {TECHNIQUE_TEXT[t['technique']]}. Ciri visual: {t['visual']}"
    if t.get("distinguish"):
        visual += f" Pembeda: {t['distinguish']}"
    culture = f"{t['name']} ({t['province']}). Budaya dan makna: {t['culture']}"
    if t.get("uncertain"):
        culture += " Belum pasti: " + " ".join(t["uncertain"])
    return {"visual": visual, "budaya": culture}


def load_catalog(session: Session, embedder: Embedder | None, catalog: dict) -> dict:
    traditions = validate(catalog)
    created_entries = reused_entries = chunks = 0
    for t in traditions:
        entry = session.scalar(select(GalleryEntry).where(GalleryEntry.name == t["name"]))
        if entry is None:
            entry = gallery_svc.create_entry(
                session, None, name=t["name"], textile_type=TECHNIQUE_TEXT[t["technique"]],
                technique=TECHNIQUE_TEXT[t["technique"]], region=t["province"],
                community=t.get("community"), summary=t["visual"][:280])
            created_entries += 1
        else:
            reused_entries += 1
        source = session.scalar(select(CulturalSource).where(CulturalSource.title == dossier_title(t["name"])))
        listing = "\n".join(f"- {s.get('title') or s['url']} ({s.get('publisher') or '-'}): {s['url']}"
                            for s in t["sources"])
        if source is None:
            source = gallery_svc.create_source(
                session, None, title=dossier_title(t["name"]),
                publisher=f"Tenara, dirangkum dari {len(t['sources'])} sumber web",
                url=t["sources"][0]["url"], license=LICENSE,
                rights_notes=f"Riset web otomatis (AI) {catalog.get('researched_at', '')}. Sumber:\n{listing}")
        else:
            source.rights_notes = f"Riset web otomatis (AI) {catalog.get('researched_at', '')}. Sumber:\n{listing}"
        session.execute(delete(SourceChunk).where(SourceChunk.source_id == source.id))
        for aspect, text in chunk_texts(t).items():
            meta = {"catalog": "tenun_catalog", "aspect": aspect, "tradition": t["name"],
                    "province": t["province"], "region": t.get("region"), "technique": t["technique"],
                    "sources": t["sources"], "uncertain": t.get("uncertain") or [],
                    "embed_model": getattr(embedder, "name", None)}
            gallery_svc.add_chunk(session, source, text=text, entry_id=entry.id, meta=meta,
                                  locator=f"{t['name']} / {aspect}", embedder=embedder)
            chunks += 1
    session.flush()
    return {"traditions": len(traditions), "entries_created": created_entries,
            "entries_reused": reused_entries, "chunks": chunks,
            "provinces": len({t["province"] for t in traditions})}


def approve_catalog(session: Session, reviewer_email: str, catalog: dict) -> int:
    reviewer = session.scalar(select(User).join(RoleAssignment, RoleAssignment.user_id == User.id).where(
        User.email == reviewer_email, RoleAssignment.role == "admin", RoleAssignment.status == "active"))
    if reviewer is None:
        raise SystemExit(f"{reviewer_email} is not an active admin; only a curator may approve sources")
    approved = 0
    for t in validate(catalog):
        source = session.scalar(select(CulturalSource).where(CulturalSource.title == dossier_title(t["name"])))
        if source is not None and source.approval_status == "pending":
            gallery_svc.decide_source(session, reviewer, source, "approve",
                                      "Ditinjau kurator sebelum dipakai untuk scan dan cerita")
            approved += 1
    return approved


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--approve-by", metavar="ADMIN_EMAIL",
                    help="approve every catalog dossier as this curator (after reviewing the file)")
    args = ap.parse_args()
    catalog = json.loads(CATALOG.read_text())
    with SessionLocal() as session:
        print(load_catalog(session, get_embedder(), catalog))
        if args.approve_by:
            print("approved:", approve_catalog(session, args.approve_by, catalog))
        session.commit()


if __name__ == "__main__":
    main()
