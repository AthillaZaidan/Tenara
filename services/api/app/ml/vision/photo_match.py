"""Check a seller's tradition claim against curator-approved reference photos (local, no LLM).

The listing's Gallery entry is the seller's claim. The photo is embedded with SigLIP 2 (five motif
crops, averaged) and compared with APPROVED reference photos. A tradition is judged only when it has
at least MIN_REFS modern references from at least MIN_SOURCES different sources; its score is the
mean similarity of its TOP_M nearest references.

    konsisten            the claimed tradition scores highest among the judged traditions
    perlu_dicek          another judged tradition scores higher, or the photo is a near-copy of a
                         reference photo (then it cannot show the seller's own cloth)
    belum_ada_referensi  the claimed tradition is not judged yet; a curator checks by hand

Never a verification: the curator decides; the result only helps them look.

Why these rules (experiments/vlm_eval, strict test: references from another source than the photo):
  - "claimed tradition ranks first" accepted 63% of true claims and 7% of false ones on museum and
    Commons photos; accepting anything within 0.01 of the best raised false acceptances to 21%.
  - References from museum archives did NOT transfer to modern photos of new cloth: there the same
    rule accepted 5% of true claims and 19% of false ones, and no similarity floor separated those
    photos. So only 'modern' references give a verdict; 'archival' ones are shown for comparison.
"""
import io
import logging
from datetime import UTC, datetime
from functools import lru_cache
from typing import Protocol

import numpy as np
from PIL import Image, ImageOps
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ServiceUnavailable
from app.models import File, GalleryEntry, ListingImage, ReferencePhoto
from app.models.gallery import PHOTO_DIM
from app.services.files import signed_url

log = logging.getLogger(__name__)

TOP_M = 3
MIN_REFS = 5
MIN_SOURCES = 2
NEAR_COPY = 0.97
SHOWN = 3
CROPS = [(0.5, 0.5), (0.3, 0.3), (0.7, 0.3), (0.3, 0.7), (0.7, 0.7)]

MESSAGES = {
    "konsisten": "Foto konsisten dengan foto referensi {claim}. Ini sinyal bantu, bukan verifikasi; "
                 "kurator tetap memutuskan.",
    "perlu_dicek": "Foto kurang mirip dengan foto referensi {claim} dibanding tradisi lain; "
                   "kurator perlu memeriksa.",
    "belum_ada_referensi": "Belum ada cukup foto referensi modern untuk {claim} (minimal "
                           f"{MIN_REFS} foto dari {MIN_SOURCES} sumber); kurator memeriksa manual.",
    "gagal": "Pemeriksaan foto terhadap referensi gagal dijalankan; kurator memeriksa manual.",
}
NEAR_COPY_NOTE = ("Foto ini hampir identik dengan foto referensi ({credit}); pastikan foto memang "
                  "kain milik penjual.")


class PhotoEmbedder(Protocol):
    name: str

    def embed(self, image: bytes) -> list[float]: ...


def motif_crops(image: bytes) -> list[Image.Image]:
    """Five half-size crops, so the motif weighs more than background and framing."""
    img = ImageOps.autocontrast(Image.open(io.BytesIO(image)).convert("RGB"))
    w, h = img.size
    side = max(1, int(min(w, h) * 0.5))
    out = []
    for cx, cy in CROPS:
        x, y = max(0, int(cx * w - side / 2)), max(0, int(cy * h - side / 2))
        out.append(img.crop((x, y, x + side, y + side)))
    return out


class SiglipPhotoEmbedder:
    """SigLIP 2 image vectors via fastembed/ONNX; the model loads on first use."""

    def __init__(self, model_name: str):
        self.name = model_name
        self._model = None

    def embed(self, image: bytes) -> list[float]:
        if self._model is None:
            from fastembed import ImageEmbedding

            self._model = ImageEmbedding(self.name)
        vecs = np.array(list(self._model.embed(motif_crops(image))), dtype=np.float32)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        mean = vecs.mean(axis=0)
        return [float(x) for x in mean / np.linalg.norm(mean)]


class FakePhotoEmbedder:
    """Deterministic colour layout (16x16 RGB, centred) for tests and offline development."""

    name = "fake-colour-v1"

    def embed(self, image: bytes) -> list[float]:
        img = Image.open(io.BytesIO(image)).convert("RGB").resize((16, 16))
        vec = np.asarray(img, dtype=np.float32).reshape(-1) / 255.0 - 0.5
        assert vec.size == PHOTO_DIM
        norm = np.linalg.norm(vec) or 1.0
        return [float(x) for x in vec / norm]


@lru_cache
def get_photo_embedder() -> PhotoEmbedder | None:
    if settings.photo_embedder == "fastembed":
        return SiglipPhotoEmbedder(settings.photo_embedding_model)
    if settings.photo_embedder == "fake":
        return FakePhotoEmbedder()
    return None


def _approved(model: str):
    return (ReferencePhoto.approval_status == "approved") & (ReferencePhoto.embed_model == model)


def judged_entries(session: Session, model: str) -> set:
    """Entries with enough approved modern references from enough sources to give a verdict."""
    rows = session.execute(
        select(ReferencePhoto.entry_id)
        .where(_approved(model), ReferencePhoto.style == "modern")
        .group_by(ReferencePhoto.entry_id)
        .having((func.count() >= MIN_REFS)
                & (func.count(func.distinct(ReferencePhoto.source_label)) >= MIN_SOURCES)))
    return {r[0] for r in rows}


def _scores(session: Session, model: str, vec: list[float], entries: set) -> dict:
    """Mean similarity of each judged entry's TOP_M nearest modern references (near-copies left out)."""
    if not entries:
        return {}
    distance = ReferencePhoto.embedding.cosine_distance(vec)
    ranked = (select(ReferencePhoto.entry_id, (1 - distance).label("sim"),
                     func.row_number().over(partition_by=ReferencePhoto.entry_id,
                                            order_by=distance).label("rn"))
              .where(_approved(model), ReferencePhoto.style == "modern",
                     ReferencePhoto.entry_id.in_(entries), distance > 1 - NEAR_COPY)
              .subquery())
    sims: dict = {}
    for entry_id, sim in session.execute(select(ranked.c.entry_id, ranked.c.sim)
                                         .where(ranked.c.rn <= TOP_M)):
        sims.setdefault(entry_id, []).append(float(sim))
    return {e: sum(v) / len(v) for e, v in sims.items()}


def _near_copy(session: Session, model: str, vec: list[float]) -> ReferencePhoto | None:
    distance = ReferencePhoto.embedding.cosine_distance(vec)
    return session.scalar(select(ReferencePhoto).where(_approved(model), distance <= 1 - NEAR_COPY)
                          .order_by(distance).limit(1))


def _comparisons(session: Session, model: str, vec: list[float], entry: GalleryEntry) -> list[dict]:
    """Nearest displayable references of the claimed tradition, modern or archival, for the curator."""
    distance = ReferencePhoto.embedding.cosine_distance(vec)
    rows = session.execute(
        select(ReferencePhoto, (1 - distance).label("sim"))
        .where(_approved(model), ReferencePhoto.entry_id == entry.id, ReferencePhoto.display_allowed,
               ReferencePhoto.file_id.is_not(None))
        .order_by(distance).limit(SHOWN)).all()
    out = []
    for ref, sim in rows:
        file = session.get(File, ref.file_id)
        if file is None or file.deleted_at is not None:
            continue
        out.append({"id": str(ref.id), "style": ref.style, "similarity": round(float(sim), 3),
                    "credit": ref.credit, "license": ref.license, "source_url": ref.source_url,
                    "url": signed_url(file)})
    return out


def check_claim(session: Session, embedder: PhotoEmbedder | None, image: bytes,
                claimed: GalleryEntry | None) -> dict | None:
    """Result for the listing's claimed tradition, or None when the photo check is switched off."""
    if embedder is None:
        return None
    claim = claimed.name if claimed else "tradisi yang diklaim"
    base = {"method": embedder.name, "claimed": claimed.name if claimed else None,
            "claimed_entry_id": str(claimed.id) if claimed else None, "rank": None,
            "top": [], "comparisons": [], "notes": []}
    try:
        vec = embedder.embed(image)
        entries = judged_entries(session, embedder.name)
        scores = _scores(session, embedder.name, vec, entries)
        copy = _near_copy(session, embedder.name, vec)
        comparisons = _comparisons(session, embedder.name, vec, claimed) if claimed else []
    except Exception:
        log.exception("photo claim check failed")
        return {**base, "status": "gagal", "message": MESSAGES["gagal"]}
    ranked = sorted(scores, key=scores.get, reverse=True)
    names = {e.id: e.name for e in session.scalars(select(GalleryEntry).where(GalleryEntry.id.in_(ranked)))}
    top = [{"tradition": names.get(e), "score": round(scores[e], 3)} for e in ranked[:3]]
    notes = [NEAR_COPY_NOTE.format(credit=copy.credit or copy.source_label)] if copy else []
    if claimed is None or claimed.id not in scores:
        status, rank = "belum_ada_referensi", None
    else:
        rank = ranked.index(claimed.id) + 1
        status = "konsisten" if rank == 1 and not copy else "perlu_dicek"
    return {**base, "status": status, "message": MESSAGES[status].format(claim=claim), "rank": rank,
            "top": top if status != "belum_ada_referensi" else [], "comparisons": comparisons,
            "notes": notes}


def add_reference(session: Session, embedder: PhotoEmbedder, *, entry: GalleryEntry, image: bytes,
                  style: str, source_label: str, file_id=None, listing_id=None,
                  source_url: str | None = None, external_id: str | None = None,
                  credit: str | None = None, license: str | None = None,
                  display_allowed: bool = False) -> ReferencePhoto:
    ref = ReferencePhoto(entry_id=entry.id, file_id=file_id, listing_id=listing_id, style=style,
                         source_label=source_label[:200], source_url=source_url, external_id=external_id,
                         credit=(credit or None) and credit[:300], license=(license or None) and license[:100],
                         display_allowed=display_allowed, embedding=embedder.embed(image),
                         embed_model=embedder.name)
    session.add(ref)
    session.flush()
    return ref


def add_listing_references(session: Session, storage, embedder: PhotoEmbedder | None, listing,
                           curator) -> int:
    """After a curator verifies a listing: its photos become approved modern references for the
    listing's Gallery entry. One merchant counts as one source; never displayed to other users."""
    if embedder is None:
        raise ServiceUnavailable("Pembanding foto belum dikonfigurasi (PHOTO_EMBEDDER)")
    entry = session.get(GalleryEntry, listing.entry_id)
    added = 0
    images = session.scalars(select(ListingImage).where(ListingImage.listing_id == listing.id)
                             .order_by(ListingImage.sort_order, ListingImage.id))
    for li in images:
        key = f"listing:{listing.id}:{li.file_id}"
        file = session.get(File, li.file_id)
        if file is None or file.deleted_at is not None or session.scalar(
                select(ReferencePhoto.id).where(ReferencePhoto.external_id == key)):
            continue
        ref = add_reference(session, embedder, entry=entry, image=storage.open(file.storage_key),
                            style="modern", source_label=f"merchant:{listing.merchant_id}",
                            file_id=file.id, listing_id=listing.id, external_id=key,
                            credit="Foto penjual, diverifikasi kurator", display_allowed=False)
        ref.approval_status, ref.decided_by, ref.decided_at = "approved", curator.id, datetime.now(UTC)
        added += 1
    session.flush()
    return added
