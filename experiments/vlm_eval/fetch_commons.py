#!/usr/bin/env python3
"""Collect modern, openly licensed photos of Indonesian woven textiles from Wikimedia Commons categories.

Museum photos (fetch_museum.py) are archival; a seller's photo looks more like a modern phone photo of
cloth. Commons categories hold many of those. A category gives the label only when it names one
tradition; mixed categories (e.g. "Tenun") are labelled from the file title with the same rules as the
museum fetcher, and skipped when the title names none. Commons hosts only free licences; the licence
and author are kept per file. Tais (Timor-Leste) and pua kumbu (mostly Sarawak) are skipped: their
country of origin does not match an Indonesian tradition label.

Each file's uploader is recorded: the evaluation treats one uploader as one source, so a photographer's
own photos never serve as each other's reference. Photos of people, buildings or looms are dropped by
title and then by a CLIP zero-shot check (cloth close-up vs. other scenes).

Writes data/tenun_datasets/commons/manifest.json (git-ignored). Descriptive User-Agent, as Wikimedia's
API policy asks; about one API request per second.
Run from services/api:  uv run python ../../experiments/vlm_eval/fetch_commons.py
"""
import json
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_museum import NOT_CLOTH, label_of

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/tenun_datasets/commons"
API = "https://commons.wikimedia.org/w/api.php"
UA = "TenaraEval/0.1 (student research script; Wikimedia Commons textile photos)"

# category -> label (None = label from the title); depth = how far to follow subcategories
CATEGORIES = [
    ("Ulos", "Ulos Batak Toba", 1), ("Ragidup", "Ulos Batak Toba", 1),
    ("Sumba ikat", "Tenun Ikat Sumba", 2), ("Textiles of Sumba", "Tenun Ikat Sumba", 1),
    ("Geringsing", "Gringsing Tenganan", 1),
    ("Tapis (Indonesian textile)", "Tapis Lampung", 1), ("Palepai", "Tapis Lampung", 1),
    ("Tampan (ship cloth)", "Tapis Lampung", 1),
    ("Songket in South Sumatra", "Songket Palembang", 1),
    ("Songket in West Sumatra", "Songket Minangkabau (Pandai Sikek dan Silungkang)", 1),
    ("Lombok ikat", "Tenun Sasak Lombok", 1), ("Cual cloth", "Tenun Cual Bangka Belitung", 1),
    ("Lurik", "Lurik", 1), ("Ulap Doyo", "Ulap Doyo", 1),
    ("Tenun", None, 0), ("Indonesian ikat", None, 0), ("Close-up photographs of ikat", None, 0),
    ("Textiles of Bali", None, 1), ("Songket in Indonesia", None, 1),
]
SKIP_CATS = re.compile(r"tais|timor-leste|east timor|pua kumbu|sarawak|malaysia|weavers|market|making|dance", re.IGNORECASE)
# title-based labels for traditions the museum rules do not know
EXTRA_RULES = [("Lurik", r"\blurik\b"), ("Tenun Sasak Lombok", r"\blombok\b|\bsasak\b"),
               ("Tenun Cual Bangka Belitung", r"\bcual\b"), ("Ulap Doyo", r"\bdoyo\b"),
               ("Songket Minangkabau (Pandai Sikek dan Silungkang)", r"pandai sikek|silungkang"),
               ("Tenun Ikat Troso", r"\btroso\b"), ("Tenun Gedog Tuban", r"\bgedog\b|\btuban\b")]
# found by looking at a contact sheet of the first run: parades, a wedding, an exhibition hall, bamboo cloth
NOT_CLOTH_COMMONS = re.compile(r"prajurit|grebeg|wedding|pernikahan|pameran|exhibition|bamboo", re.IGNORECASE)
FREE = re.compile(r"^(cc0|public domain|pd|cc[ -]by(-sa)?( \d\.\d)?)", re.IGNORECASE)


def api(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode(params | {"format": "json", "maxlag": "5"})
    for attempt in range(4):  # maxlag / rate-limit answers are retried, then reported
        out = subprocess.run(["curl", "-s", "--max-time", "30", "-A", UA, url], capture_output=True, check=False)
        time.sleep(1.0 + 4 * attempt)
        try:
            d = json.loads(out.stdout or b"{}")
        except ValueError:
            d = {"error": {"info": out.stdout[:120]}}
        if "error" not in d:
            return d
    print("commons api failed:", d["error"], flush=True)
    return {}


def members(cat: str, kind: str) -> list[str]:
    titles, cont = [], {}
    while True:
        d = api({"action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat, "cmtype": kind,
                 "cmlimit": "500"} | cont)
        titles += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        if "continue" not in d:
            return titles
        cont = d["continue"]


def files_of(cat: str, depth: int, seen: set) -> list[str]:
    if cat in seen:
        return []
    seen.add(cat)
    out = members(cat, "file")
    if depth > 0:
        for sub in members(cat, "subcat"):
            name = sub.removeprefix("Category:")
            if not SKIP_CATS.search(name):
                out += files_of(name, depth - 1, seen)
    return out


def title_label(title: str) -> str | None:
    t = title.lower()
    for label, pattern in EXTRA_RULES:
        if re.search(pattern, t):
            return label
    return label_of(title)


def info(titles: list[str]) -> dict:
    """imageinfo for up to 50 files per request: 960px thumb, licence, author, uploader."""
    result = {}
    for k in range(0, len(titles), 50):
        d = api({"action": "query", "prop": "imageinfo", "titles": "|".join(titles[k:k + 50]),
                 "iiprop": "url|user|extmetadata|mime", "iiurlwidth": "960"})
        for p in d.get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            meta = ii.get("extmetadata") or {}
            result[p["title"]] = {"thumb": ii.get("thumburl"), "user": ii.get("user"), "mime": ii.get("mime"),
                                  "url": ii.get("descriptionurl"),
                                  "license": (meta.get("LicenseShortName") or {}).get("value", ""),
                                  "artist": re.sub("<[^>]+>", "", (meta.get("Artist") or {}).get("value", ""))[:120]}
    return result


def clothlike(paths: list[Path]) -> list[bool]:
    """CLIP zero-shot: is this a close-up of woven cloth rather than people, a building or a loom?"""
    import numpy as np
    from fastembed import ImageEmbedding, TextEmbedding

    prompts = ["a close-up photo of a woven textile", "a photo of a patterned fabric laid flat",
               "a photo of people", "a portrait of a person wearing traditional clothes",
               "a photo of a building", "a photo of a weaving loom", "a photo of a market stall"]
    t = np.array(list(TextEmbedding("Qdrant/clip-ViT-B-32-text").embed(prompts)))
    v = np.array(list(ImageEmbedding("Qdrant/clip-ViT-B-32-vision").embed([str(p) for p in paths])))
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    logits = 100 * v @ t.T
    probs = np.exp(logits - logits.max(1, keepdims=True))
    probs /= probs.sum(1, keepdims=True)
    return list(probs[:, :2].sum(1) >= 0.5)


def main() -> None:
    from fetch_museum import _fetch_image

    OUT.mkdir(parents=True, exist_ok=True)
    candidates, seen_cats = {}, set()
    for cat, label, depth in CATEGORIES:
        for title in files_of(cat, depth, seen_cats):
            lab = label or title_label(title)
            if lab and title not in candidates and not re.search(NOT_CLOTH, title.lower()) \
                    and not NOT_CLOTH_COMMONS.search(title):
                candidates[title] = {"label": lab, "category": cat}
        print(f"{cat}: {len(candidates)} candidates so far", flush=True)
    meta = info(list(candidates))
    print("imageinfo:", len(meta), "of", len(candidates), flush=True)
    kept = []
    for title, c in candidates.items():
        m = meta.get(title) or {}
        if not m.get("thumb") or m.get("mime") not in ("image/jpeg", "image/png", "image/tiff") \
                or not FREE.search(m["license"].strip()):
            continue
        fid = re.sub(r"[^A-Za-z0-9]+", "_", title.removeprefix("File:"))[:80]
        path = OUT / f"cm-{fid}.jpg"
        if (path.exists() and path.stat().st_size > 0) or _fetch_image(m["thumb"], path):
            time.sleep(0.3)
            kept.append({"source": "commons/" + (m["user"] or "?"), "id": "commons/" + (m["user"] or "?"),
                         "label": c["label"], "title": title, "category": c["category"], "file": path.name,
                         "url": m["url"], "license": m["license"], "creator": m["artist"]})
    ok = clothlike([OUT / k["file"] for k in kept]) if kept else []
    final = [k for k, good in zip(kept, ok, strict=True) if good]
    for k, good in zip(kept, ok, strict=True):
        if not good:
            (OUT / k["file"]).unlink(missing_ok=True)
    (OUT / "manifest.json").write_text(json.dumps(final, indent=1, ensure_ascii=False))
    from collections import Counter

    print("candidates:", len(candidates), "downloaded:", len(kept), "cloth-like:", len(final))
    print(Counter(k["label"] for k in final).most_common())
    print("uploaders:", len({k["source"] for k in final}))


if __name__ == "__main__":
    main()
