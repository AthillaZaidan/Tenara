"""Vision-language analysis of a seller's fabric photo. Output is a suggestion for the merchant to
confirm; it never sets curator-verified origin and never claims authenticity."""
import base64
import json
import urllib.error
import urllib.request
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ServiceUnavailable
from app.models import CvAnalysis, FabricListing, User

TECHNIQUES = ["ikat", "songket", "plain_weave", "printed_or_batik", "other", "unknown"]
CATEGORIES = ["fauna", "flora", "geometric", "figurative", "mixed", "other", "unknown"]
CONFIDENCE = ["low", "medium", "high"]


class VLMClient(Protocol):
    name: str

    def analyze(self, image: bytes, content_type: str, candidates: list[str]) -> dict: ...


PROMPT = ("You analyse a photo of an Indonesian traditional textile for a marketplace seller. Describe "
          "only what is visible; use 'unknown' when unsure. Reply with JSON only: "
          '{"technique": one of %s, "motif_category": one of %s, "dominant_colors": [max 3 plain words], '
          '"candidate_matches": [up to 3 names chosen ONLY from the candidate list, best first], '
          '"origin_guess": string or null, "origin_confidence": one of %s, '
          '"is_traditional_woven_textile": boolean}. This is a suggestion a human will verify.')


class OpenAICompatVLM:
    def __init__(self):
        self.name = f"{settings.llm_provider}:{settings.llm_model}"

    def _endpoint(self) -> tuple[str, str]:
        table = {"openai": ("https://api.openai.com/v1", settings.openai_api_key),
                 "openrouter": ("https://openrouter.ai/api/v1", settings.openrouter_api_key),
                 "ollama": ("http://localhost:11434/v1", "")}
        return table[settings.llm_provider]

    def analyze(self, image: bytes, content_type: str, candidates: list[str]) -> dict:
        base, key = self._endpoint()
        url = f"data:{content_type};base64,{base64.b64encode(image).decode()}"
        body = {"model": settings.llm_model, "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": PROMPT % (TECHNIQUES, CATEGORIES, CONFIDENCE)
                     + " Candidates: " + json.dumps(candidates)},
                    {"type": "image_url", "image_url": {"url": url}}]}]}
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(body).encode(),
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=settings.vlm_timeout_seconds) as resp:
                return json.loads(json.load(resp)["choices"][0]["message"]["content"])
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:200]
            raise RuntimeError(f"Penyedia VLM menolak permintaan (HTTP {exc.code}): {detail}") from exc
        except (OSError, KeyError, ValueError) as exc:
            raise RuntimeError(f"Penyedia VLM tidak dapat dihubungi/dibaca: {exc}") from exc


def get_vlm() -> VLMClient | None:
    provider = settings.llm_provider
    configured = provider == "ollama" or (
        provider == "openai" and settings.openai_api_key) or (
        provider == "openrouter" and settings.openrouter_api_key)
    return OpenAICompatVLM() if configured else None


def _enum(value, allowed: list[str]) -> str:
    return value if value in allowed else "unknown" if "unknown" in allowed else allowed[0]


def normalize(raw: dict, candidates: list[str]) -> dict:
    """Server-side clean-up: only known enum values, only candidates from our own list."""
    matches = [c for c in (raw.get("candidate_matches") or []) if c in candidates][:3]
    colors = [str(c)[:30] for c in (raw.get("dominant_colors") or [])][:3]
    origin = raw.get("origin_guess")
    return {
        "technique": _enum(raw.get("technique"), TECHNIQUES),
        "motif_category": _enum(raw.get("motif_category"), CATEGORIES),
        "dominant_colors": colors, "candidate_matches": matches,
        "origin_guess": str(origin)[:120] if origin else None,
        "origin_confidence": _enum(raw.get("origin_confidence"), CONFIDENCE) if origin else "low",
        "is_traditional_woven_textile": bool(raw.get("is_traditional_woven_textile", False)),
    }


def run_analysis(session: Session, user: User, listing: FabricListing | None, file_id,
                 image: bytes, content_type: str, vlm: VLMClient | None,
                 candidates: list[str]) -> CvAnalysis:
    if vlm is None:
        raise ServiceUnavailable("Penganalisis visual belum dikonfigurasi (tidak ada API key/provider)")
    try:
        result = normalize(vlm.analyze(image, content_type, candidates), candidates)
    except RuntimeError as exc:
        row = CvAnalysis(owner_id=user.id, listing_id=listing.id if listing else None,
                         file_id=file_id, status="failed", method=vlm.name, error=str(exc))
        session.add(row)
        session.commit()  # keep the failure on record; never fabricate a result
        raise ServiceUnavailable(str(exc)) from exc
    row = CvAnalysis(owner_id=user.id, listing_id=listing.id if listing else None, file_id=file_id,
                     status="completed", method=vlm.name, result=result)
    session.add(row)
    session.flush()
    if listing is not None:
        listing.visual_match = {"status": "suggestion", "analysis_id": str(row.id),
                                "method": vlm.name, "needs_merchant_review": True, **result}
    session.flush()
    return row


def analysis_out(row: CvAnalysis) -> dict:
    return {"id": row.id, "status": row.status, "method": row.method, "result": row.result,
            "error": row.error,
            "notice": "Saran visual otomatis. Bukan sertifikasi asal-usul; penjual mengonfirmasi "
                      "dan kurator memverifikasi klaim budaya."}
