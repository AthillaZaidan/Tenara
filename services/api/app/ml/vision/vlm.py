"""Fabric scan for sellers: describe the photo, then check it against the seller's own claim.

The seller's claim is the listing's Gallery entry (plus their free-text claimed origin). The scan
never names a tradition by itself:

1. describe   (vision model, photo only): technique, motif elements, colours, distinctive features.
2. technique  (local rule): is the technique the model sees the one the catalog gives for the claimed
              tradition? A mismatch asks the curator to look; it is not an accusation.
3. photo      (local, SigLIP 2, see photo_match): is the photo consistent with curator-approved
              reference photos of the claimed tradition?

Why no tradition guess (experiments/vlm_eval): a writer/critic that picked one of up to 8 catalog
traditions said "match" with the wrong tradition on 9 of 13 test photos (Gemma 4 26B and 31B), and
checking a claim against the catalog text accepted look-alike false claims (Sikka photo claimed as
Ende-Lio or Sumba) as often as true ones (10/13 vs 9-10/13). The technique, though, was right on 11
of 13 photos, and a claim with another technique was rejected 12 of 13 times.

Everything here is a signal for the merchant and the curator; curator-verified origin is never set.
"""
import base64
import io
from typing import Protocol

from PIL import Image
from sqlalchemy.orm import Session

from app.core.errors import ServiceUnavailable
from app.ml import llm_client
from app.ml.vision import photo_match
from app.ml.vision.photo_match import PhotoEmbedder
from app.models import CvAnalysis, FabricListing, GalleryEntry, User

TECHNIQUES = ["ikat", "songket", "plain_weave", "printed_or_batik", "other", "unknown"]
CATEGORIES = ["fauna", "flora", "geometric", "figurative", "mixed", "other", "unknown"]
TECHNIQUE_TEXT = {"ikat": "tenun ikat", "songket": "songket", "plain_weave": "tenun polos atau lurik",
                  "printed_or_batik": "kain cetak atau batik", "other": "tenun lain", "unknown": "tidak jelas"}
MAX_SIDE = 1024

DESCRIBE_PROMPT = (
    "You examine a photo of an Indonesian textile for a marketplace seller. Describe only what is "
    "visible; use 'unknown' when unsure. Reply with JSON only: "
    '{"technique": one of %s, "motif_category": one of %s, '
    '"motif_elements": [up to 6 short Indonesian phrases, e.g. "kuda", "belah ketupat"], '
    '"dominant_colors": [up to 3 plain Indonesian colour words], '
    '"distinctive_features": [up to 5 short Indonesian phrases on layout, borders, thread, sheen], '
    '"is_traditional_woven_textile": boolean}.')

TECHNIQUE_MESSAGES = {
    "cocok": "Teknik yang terlihat ({seen}) sesuai dengan katalog {claim}.",
    "berbeda": "Teknik yang terlihat ({seen}) berbeda dengan katalog {claim} ({expected}); kurator perlu "
               "memeriksa. Deteksi teknik bisa keliru (sekitar 2 dari 13 foto uji).",
    "tidak_jelas": "Teknik belum bisa dibandingkan dengan katalog {claim}.",
}


class VLMClient(Protocol):
    name: str

    def describe(self, image: bytes, content_type: str) -> dict: ...


def _image_part(image: bytes, content_type: str) -> dict:
    return {"type": "image_url",
            "image_url": {"url": f"data:{content_type};base64,{base64.b64encode(image).decode()}"}}


class OpenAICompatVLM:
    """Describes the photo on LLM_MODEL through the shared OpenAI-compatible client."""

    def __init__(self):
        self.name = llm_client.provider_name()

    def describe(self, image: bytes, content_type: str) -> dict:
        prompt = DESCRIBE_PROMPT % (TECHNIQUES, CATEGORIES)
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt},
                                                 _image_part(image, content_type)]}]
        return llm_client.parse_json(llm_client.chat(messages).content, "deskripsi")


def get_vlm() -> VLMClient | None:
    return OpenAICompatVLM() if llm_client.configured() else None


# ---------- normalisation ----------

def _enum(value, allowed: list[str]) -> str:
    return value if value in allowed else "unknown" if "unknown" in allowed else allowed[0]


def _texts(value, limit: int, length: int = 60) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip()[:length] for v in value if str(v).strip()][:limit]


def shrink(image: bytes, content_type: str) -> tuple[bytes, str]:
    """Downscale to MAX_SIDE so provider calls stay fast and cheap; leave unreadable bytes alone."""
    try:
        img = Image.open(io.BytesIO(image))
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        img.convert("RGB").save(out, format="JPEG", quality=88)
        return out.getvalue(), "image/jpeg"
    except OSError:
        return image, content_type


def normalize_observation(raw: dict) -> dict:
    return {
        "technique": _enum(raw.get("technique"), TECHNIQUES),
        "motif_category": _enum(raw.get("motif_category"), CATEGORIES),
        "motif_elements": _texts(raw.get("motif_elements"), 6),
        "dominant_colors": _texts(raw.get("dominant_colors"), 3, 30),
        "distinctive_features": _texts(raw.get("distinctive_features"), 5),
        "is_traditional_woven_textile": raw.get("is_traditional_woven_textile") is True,
    }


# ---------- technique vs. claim ----------

def entry_technique(entry: GalleryEntry | None) -> str | None:
    """The catalog technique of the claimed entry (ikat, songket, plain_weave), None when not specific."""
    text = (entry.technique or entry.textile_type or "").lower() if entry else ""
    for key, words in (("songket", ("songket",)), ("ikat", ("ikat",)), ("plain_weave", ("polos", "lurik"))):
        if any(w in text for w in words):
            return key
    return None


def technique_check(obs: dict, claimed: GalleryEntry | None) -> dict | None:
    if claimed is None:
        return None
    seen, expected = obs["technique"], entry_technique(claimed)
    if seen == "printed_or_batik":
        status = "berbeda"
    elif seen in ("unknown", "other") or expected is None:
        status = "tidak_jelas"
    else:
        status = "cocok" if seen == expected else "berbeda"
    message = TECHNIQUE_MESSAGES[status].format(
        seen=TECHNIQUE_TEXT[seen], claim=claimed.name,
        expected=TECHNIQUE_TEXT[expected] if expected else "tidak spesifik")
    return {"status": status, "seen": seen, "expected": expected, "claimed": claimed.name,
            "message": message}


def run_analysis(session: Session, user: User, listing: FabricListing | None, file_id,
                 image: bytes, content_type: str, vlm: VLMClient | None,
                 photo_embedder: PhotoEmbedder | None = None) -> CvAnalysis:
    if vlm is None:
        raise ServiceUnavailable("Penganalisis visual belum dikonfigurasi (tidak ada API key/provider)")
    image, content_type = shrink(image, content_type)
    try:
        obs = normalize_observation(vlm.describe(image, content_type))
    except RuntimeError as exc:
        row = CvAnalysis(owner_id=user.id, listing_id=listing.id if listing else None,
                         file_id=file_id, status="failed", method=vlm.name, error=str(exc))
        session.add(row)
        session.commit()  # keep the failure on record; never fabricate a result
        raise ServiceUnavailable(str(exc)) from exc
    claimed = session.get(GalleryEntry, listing.entry_id) if listing else None
    notes = [] if obs["is_traditional_woven_textile"] else [
        "Model menilai foto ini mungkin bukan kain tenun tradisional; kurator perlu memeriksa."]
    result = {**obs, "claimed": claimed.name if claimed else None,
              "technique_check": technique_check(obs, claimed),
              "claim_check": photo_match.check_claim(session, photo_embedder, image, claimed),
              "notes": notes}
    row = CvAnalysis(owner_id=user.id, listing_id=listing.id if listing else None, file_id=file_id,
                     status="completed", method=vlm.name, result=result)
    session.add(row)
    session.flush()
    if listing is not None:
        listing.visual_match = {"status": "scan", "analysis_id": str(row.id), "method": vlm.name, **result}
    session.flush()
    return row


def analysis_out(row: CvAnalysis) -> dict:
    return {"id": row.id, "status": row.status, "method": row.method, "result": row.result,
            "error": row.error,
            "notice": "Deskripsi dan pemeriksaan otomatis atas klaim penjual. Bukan sertifikasi "
                      "asal-usul; kurator Tenara yang memverifikasi."}
