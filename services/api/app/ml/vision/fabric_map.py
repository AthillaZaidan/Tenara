"""Fabric map: where the zones and the main motifs sit on a listing's fabric photo.

The scan vision model (LLM_VISION_MODEL) is asked for the cloth's zones (head panel, body, border,
tumpal, fringe) and up to six motifs, each with a box. In tests on two archive photos (2026-11-14) the
zones were placed well and single-motif boxes only roughly, so the map is an ESTIMATE until the
merchant confirms or corrects it. It names what is visible; it never interprets meaning.

Boxes are normalised to 0..1 as [x0, y0, x1, y1] (left, top, right, bottom) of the photo.
"""
from __future__ import annotations

import base64
import re

from app.core.config import settings
from app.ml import llm_client

METHOD = "vlm_fabric_map_v1"
ZONES = {"kepala_kain": "kepala kain", "badan": "badan kain", "pinggiran": "pinggiran", "tumpal": "tumpal",
         "rumbai": "rumbai"}
MAX_MOTIFS = 6
PROMPT = """Foto ini adalah selembar kain tenun. Petakan tata letaknya untuk penjahit.
Kembalikan JSON:
{"zones": [{"kind": "badan" | "pinggiran" | "tumpal" | "kepala_kain" | "rumbai" | "latar_luar", "box": [x0,y0,x1,y1]}],
 "motifs": [{"name": "nama singkat bahasa Indonesia, mis. manusia, kuda, burung, belah ketupat",
             "box": [x0,y0,x1,y1], "repeats": jumlah kemunculan yang terlihat}]}
Koordinat box dinormalisasi 0-1000 terhadap lebar (x) dan tinggi (y) foto, x0,y0 kiri-atas.
"latar_luar" = bagian foto yang bukan kain. Untuk motif, beri box SATU contoh motif yang paling jelas.
Maksimal 6 motif. Hanya sebut apa yang terlihat; jangan menebak makna."""


def available() -> bool:
    return llm_client.configured()


def locate(image: bytes, content_type: str) -> dict:
    """Raw zones and motifs from the vision model (boxes in 0..1000)."""
    part = {"type": "image_url",
            "image_url": {"url": f"data:{content_type};base64,{base64.b64encode(image).decode()}"}}
    messages = [{"role": "user", "content": [{"type": "text", "text": PROMPT}, part]}]
    result = llm_client.chat(messages, model=settings.llm_vision_model or settings.llm_model)
    return llm_client.parse_json(result.content, "peta kain")


def _box(raw) -> list[float] | None:
    try:
        x0, y0, x1, y1 = (min(1.0, max(0.0, float(v) / 1000)) for v in raw)
    except (TypeError, ValueError):
        return None
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    if x1 - x0 < 0.02 or y1 - y0 < 0.02:  # a sliver cannot be cut from or shown
        return None
    return [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)]


def label_key(text: str) -> str:
    """What a buyer might type for a region: lower case, reduplication folded ("burung-burung" -> "burung")."""
    text = re.sub(r"\b(\w+)-\1\b", r"\1", text.strip().lower())
    return re.sub(r"\s+", " ", text)


def normalise(raw: dict) -> list[dict]:
    """Regions with stable ids: zones first (z1..), then motifs (m1..); unknown kinds and bad boxes dropped."""
    regions, seen = [], set()
    for z in raw.get("zones") or []:
        label, box = ZONES.get(str(z.get("kind", ""))), _box(z.get("box"))
        if label and box and label not in seen:
            seen.add(label)
            regions.append({"id": f"z{len(seen)}", "kind": "zone", "label": label, "box": box, "repeats": None})
    motifs = 0
    for m in raw.get("motifs") or []:
        label, box = label_key(str(m.get("name", ""))), _box(m.get("box"))
        if not label or not box or label in seen or motifs >= MAX_MOTIFS:
            continue
        seen.add(label)
        motifs += 1
        try:
            repeats = max(1, int(m.get("repeats") or 1))
        except (TypeError, ValueError):
            repeats = 1
        regions.append({"id": f"m{motifs}", "kind": "motif", "label": label[:40], "box": box, "repeats": repeats})
    return regions
