"""Load labelled tenun photos as reference photos for the seller claim check (app/ml/vision/photo_match).

Sources (all under data/tenun_datasets/, local only, git-ignored):
  museum/manifest.json    The Met / Openverse (experiments/vlm_eval/fetch_museum.py)   -> archival
  commons/manifest.json   Wikimedia Commons (experiments/vlm_eval/fetch_commons.py)    -> archival
  mendeley_sikka_v3       Sikka motif photos, CC BY 4.0                                 -> modern
  mendeley_ntt_534 / mendeley_bali_336   originals only, licence not recorded           -> modern, hidden
  --folder DIR            your own photos of one tradition (e.g. taken at a gallery)    -> modern

Only photos whose label is a Gallery entry name (data/tenun_catalog.json, scripts.seed_catalog) are
loaded; others are counted and skipped. Everything stays PENDING until a curator approves it (admin
page or --approve-by). Re-running skips photos already loaded (external_id). Archival photos never
give a verdict; they are shown to the curator for comparison when their licence allows.

    uv run python -m scripts.seed_reference_photos --owner admin@x.id
    uv run python -m scripts.seed_reference_photos --owner admin@x.id --folder ~/foto/sumba \\
        --tradition "Tenun Ikat Sumba" --source-label "Tim Tenara, Pameran X 2026"
    uv run python -m scripts.seed_reference_photos --owner admin@x.id --approve-by admin@x.id
"""
import argparse
import io
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.ml.vision import photo_match
from app.ml.vision.photo_match import PhotoEmbedder, get_photo_embedder
from app.models import GalleryEntry, ReferencePhoto, RoleAssignment, User
from app.services.files import create_file
from app.services.storage import Storage, get_storage

DATA = Path(__file__).resolve().parents[3] / "data" / "tenun_datasets"
SIKKA_LICENSE = "CC BY 4.0"
SIKKA_CREDIT = "Motif Tenun Ikat Sikka dataset, Mendeley Data (CC BY 4.0)"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def _ntt_label(kabupaten: str) -> str | None:
    k = kabupaten.lower()
    if k.startswith("sumba"):
        return "Tenun Ikat Sumba"
    if "manggarai" in k:
        return "Songke Manggarai"
    return None  # other Flores regencies are not one catalog tradition


def _bali_label(jenis: str) -> str | None:
    j = " ".join(jenis.split()).lower()
    for word, label in (("songket", "Songket Bali"), ("endek", "Endek Bali"), ("gringsing", "Gringsing Tenganan")):
        if word in j:
            return label
    return None


def collect(data: Path) -> list[dict]:
    """Every labelled photo found under data/, as dicts ready for load()."""
    items = []
    for name in ("museum", "commons"):
        manifest = data / name / "manifest.json"
        if manifest.exists():
            for m in json.loads(manifest.read_text()):
                items.append({"path": data / name / m["file"], "label": m["label"], "style": "archival",
                              "source_label": m["source"], "external_id": f"{name}:{m['file']}",
                              "source_url": m.get("url"), "license": m.get("license"),
                              "credit": m.get("creator") or m.get("title") or m["source"],
                              "display_allowed": True})
    sikka = data / "mendeley_sikka_v3/extracted/sikka_motif_512"
    if sikka.exists():
        for p in sorted(sikka.glob("*/*.jpg")):
            items.append({"path": p, "label": "Tenun Ikat Sikka", "style": "modern",
                          "source_label": "mendeley-sikka-v3", "external_id": f"mendeley-sikka:{p.parent.name}/{p.name}",
                          "license": SIKKA_LICENSE, "credit": SIKKA_CREDIT, "display_allowed": True})
    for folder, meta, labeller, key in (("mendeley_ntt_534", "534 NTT motifs.json", _ntt_label, "kabupaten_kota"),
                                        ("mendeley_bali_336", "336 bali motifs.json", _bali_label, "jenis")):
        manifest = data / folder / meta
        if not manifest.exists():
            continue
        for x in json.loads(manifest.read_text()):
            p = data / folder / "originals" / x["file_original"].split("/")[-1]
            label = labeller(x[key])
            if p.exists() and label:
                items.append({"path": p, "label": label, "style": "modern", "source_label": folder,
                              "external_id": f"{folder}:{p.name}", "license": None,
                              "credit": f"{folder} (Mendeley Data); lisensi belum dicek kurator",
                              "display_allowed": False})
    return items


def folder_items(folder: Path, tradition: str, source_label: str, credit: str | None,
                 license: str | None, display: bool) -> list[dict]:
    return [{"path": p, "label": tradition, "style": "modern", "source_label": source_label,
             "external_id": f"folder:{source_label}:{p.name}", "license": license,
             "credit": credit or source_label, "display_allowed": display}
            for p in sorted(folder.iterdir()) if p.suffix.lower() in IMAGE_SUFFIXES]


def _jpeg(path: Path) -> bytes:
    img = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    img.thumbnail((1024, 1024))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88)  # re-encoded: no EXIF/location data is kept
    return out.getvalue()


def load(session: Session, storage: Storage, embedder: PhotoEmbedder, owner: User,
         items: list[dict]) -> Counter:
    entries = {e.name: e for e in session.scalars(select(GalleryEntry))}
    known = set(session.scalars(select(ReferencePhoto.external_id).where(ReferencePhoto.external_id.is_not(None))))
    stats = Counter()
    for it in items:
        entry = entries.get(it["label"])
        if entry is None:
            stats["skipped_unknown_tradition"] += 1
            continue
        if it["external_id"] in known:
            stats["skipped_already_loaded"] += 1
            continue
        data = _jpeg(it["path"])
        file = create_file(session, storage, owner_id=owner.id, kind="reference_photo", data=data,
                           content_type="image/jpeg",
                           visibility="public" if it["display_allowed"] else "private")
        photo_match.add_reference(session, embedder, entry=entry, image=data, style=it["style"],
                                  source_label=it["source_label"], file_id=file.id,
                                  source_url=it.get("source_url"), external_id=it["external_id"],
                                  credit=it.get("credit"), license=it.get("license"),
                                  display_allowed=it["display_allowed"])
        known.add(it["external_id"])
        stats[f"loaded_{it['style']}"] += 1
    return stats


def _admin(session: Session, email: str) -> User:
    user = session.scalar(select(User).join(RoleAssignment, RoleAssignment.user_id == User.id).where(
        User.email == email, RoleAssignment.role == "admin", RoleAssignment.status == "active"))
    if user is None:
        raise SystemExit(f"{email} is not an active admin")
    return user


def approve_pending(session: Session, curator: User) -> int:
    refs = list(session.scalars(select(ReferencePhoto).where(ReferencePhoto.approval_status == "pending")))
    now = datetime.now(UTC)
    for ref in refs:
        ref.approval_status, ref.decided_by, ref.decided_at = "approved", curator.id, now
    session.flush()
    return len(refs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", required=True, metavar="ADMIN_EMAIL", help="owner of the stored photo files")
    ap.add_argument("--data-dir", type=Path, default=DATA)
    ap.add_argument("--folder", type=Path, help="load only this folder of your own photos (modern)")
    ap.add_argument("--tradition", help="Gallery entry name for --folder")
    ap.add_argument("--source-label", help="who/where the --folder photos come from (one source)")
    ap.add_argument("--credit")
    ap.add_argument("--license")
    ap.add_argument("--display", action="store_true", help="--folder photos may be shown to curators/users")
    ap.add_argument("--approve-by", metavar="ADMIN_EMAIL", help="approve everything pending as this curator")
    a = ap.parse_args()
    embedder = get_photo_embedder()
    if embedder is None:
        raise SystemExit("PHOTO_EMBEDDER is 'none'")
    if a.folder and not (a.tradition and a.source_label):
        raise SystemExit("--folder needs --tradition and --source-label")
    items = folder_items(a.folder, a.tradition, a.source_label, a.credit, a.license, a.display) \
        if a.folder else collect(a.data_dir)
    with SessionLocal() as session:
        stats = load(session, get_storage(), embedder, _admin(session, a.owner), items)
        print(dict(stats))
        if a.approve_by:
            print("approved:", approve_pending(session, _admin(session, a.approve_by)))
        session.commit()


if __name__ == "__main__":
    main()
