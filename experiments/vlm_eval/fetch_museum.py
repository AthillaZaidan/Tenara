#!/usr/bin/env python3
"""Collect public-domain (CC0) Indonesian textile photos with recorded provenance from museum APIs.

Sources: The Met Collection API (CC0 public-domain works; search v1.1, paginated) and Openverse
(Wikimedia Commons archives such as KITLV and Tropenmuseum, commercial-use licences only, credit
kept per image). The Art Institute of Chicago API sits behind a bot challenge, so it is not used. Each object is labelled with a tradition only when its title/culture/place text names it;
unlabelled objects are skipped rather than guessed. Writes data/tenun_datasets/museum/manifest.json
and the images next to it (data/ is git-ignored). Plain HTTP client; no User-Agent spoofing.
"""
import json
import re
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/tenun_datasets/museum"

# order matters: the first rule whose words appear in the object text wins
RULES = [
    ("Gringsing Tenganan", r"\bg(e)?ringsing\b|tenganan"),
    ("Endek Bali", r"\bendek\b"),
    ("Songket Bali", r"\bbali(nese)?\b.*\bsongket\b|\bsongket\b.*\bbali(nese)?\b"),
    ("Tenun Ikat Sumba", r"\bsumba(nese)?\b|\bsoemba\b|\bhinggi\b|\bhingi\b|\blau pahudu\b"),
    ("Tenun Ikat Sabu (Savu Raijua)", r"\bsavu\b|\bsawu\b|\bsabu\b|\bsavoe\b|\braijua\b"),
    ("Tenun Ikat Rote", r"\broti\b|\brotti\b|\brote\b"),
    ("Tenun Timor (Amarasi, Insana, Timor Tengah Selatan)", r"\btimor(ese)?\b|\batoni\b|\bamarasi\b|\binsana\b"),
    ("Tenun Ikat Sikka", r"\bsikka\b|\bmaumere\b"),
    ("Tenun Ikat Ende-Lio", r"\bende\b|\blio\b"),
    ("Flores (lainnya)", r"\bflores\b|\bngada\b|\bmanggarai\b"),
    ("Tapis Lampung", r"\blampung\b|\blampong\b|\btapis\b|\bpalepai\b|\btampan\b|\bkauer\b|\bkroe\b"),
    ("Ulos Batak Toba", r"\bbatak(s)?\b|\bulos\b"),
    ("Songket Palembang", r"\bpalembang\b"),
    ("Songket Minangkabau (Pandai Sikek dan Silungkang)", r"\bminangkabau\b"),
    ("Tenun Sekomandi Kalumpang", r"\bgal(oe|u)mpang\b|\bkalumpang\b|\brongkong\b|\bsekomandi\b"),
    ("Tenun Toraja (Sa'dan)", r"\btoraja\b|\btoradja\b|\bsa'?dan\b"),
    ("Tenun Ikat Sintang (Dayak)", r"\biban\b|\bpua\b|\bdayak\b|\bdajak\b"),
    ("Tenun Ikat Tanimbar", r"\btanimbar\b"),
]
QUERIES = ["Sumba textile", "hinggi", "Timor textile", "Savu textile", "Roti textile", "Flores textile",
           "Lampung textile", "tampan", "palepai", "tapis", "Batak textile", "ulos", "Palembang songket",
           "Minangkabau textile", "Toraja textile", "Galumpang", "Iban pua", "Dayak textile", "Bali geringsing",
           "Bali endek", "Bali songket", "Tanimbar textile", "Indonesia ikat", "Indonesia textile"]


def get_json(url: str):
    """Plain curl (the Python default client is refused by some hosts); no header spoofing."""
    out = subprocess.run(["curl", "-s", "--max-time", "30", url], capture_output=True, check=False)
    return json.loads(out.stdout or b"null")


def label_of(text: str) -> str | None:
    t = text.lower()
    for label, pattern in RULES:
        if re.search(pattern, t):
            return label
    return None


def met() -> list[dict]:
    ids = set()
    for q in QUERIES:
        offset = 0
        while True:
            url = ("https://collectionapi.metmuseum.org/public/collection/v1.1/search?hasImages=true"
                   f"&limit=100&offset={offset}&q=" + urllib.parse.quote(q))
            try:
                page = get_json(url) or {}
            except ValueError as exc:
                print("met search failed:", q, exc)
                break
            batch = page.get("objectIDs") or []
            ids |= set(batch)
            offset += len(batch)
            if not batch or offset >= min(page.get("total") or 0, 400):
                break
            time.sleep(0.2)
    found = []
    for oid in sorted(ids):
        try:
            o = get_json(f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{oid}") or {}
        except ValueError as exc:
            print("met object failed:", oid, exc)
            continue
        time.sleep(0.05)
        if not o.get("isPublicDomain") or not o.get("primaryImageSmall"):
            continue
        if "textile" not in (o.get("classification") or "").lower() and "textile" not in (o.get("objectName") or "").lower() \
                and "cloth" not in (o.get("objectName") or "").lower() and "skirt" not in (o.get("objectName") or "").lower():
            continue
        text = " ".join(str(o.get(k) or "") for k in ("title", "culture", "country", "region", "subregion",
                                                      "locale", "geography", "objectName"))
        label = label_of(text)
        if label and "indonesia" in text.lower() or (label and o.get("country") in ("", None)):
            found.append({"source": "The Met", "id": f"met-{oid}", "label": label, "title": o.get("title"),
                          "place": text[:200], "image": o["primaryImageSmall"], "url": o.get("objectURL"),
                          "license": "CC0"})
    return found


OPENVERSE_QUERIES = ["ikatweefsel Soemba", "weefsel Soemba", "kain Soemba", "ikatweefsel Timor", "weefsel Timor",
                     "ikatweefsel Savoe", "weefsel Rotti", "ikatweefsel Flores", "weefsel Flores", "Lampong doek",
                     "tampan Lampong", "tapis Lampung", "Bataks weefsel", "ulos Batak", "songket Palembang",
                     "weefsel Palembang", "Minangkabau songket", "weefsel Toradja", "ikatweefsel Toradja",
                     "Galoempang", "Dajak weefsel", "ikatweefsel Dajak", "Tanimbar weefsel", "geringsing Bali",
                     "endek Bali", "songket Bali", "kain Bali Tropenmuseum", "Sumba hinggi textile",
                     "Timor ikat textile", "Sikka ikat", "Toraja textile", "Iban textile Kalimantan"]
# titles that show people, buildings or dyeing/weaving work rather than the cloth itself
NOT_CLOTH = (r"\bpakaian\b|\bdepan\b|\bhalak\b|\borang\b|\bpria\b|\bwanita\b|\bpenari\b|\bpengantin\b|"
             r"\brumah\b|\bpasar\b|\bvrouw(en)?\b|\bman(nen)?\b|\bmeisje|\bjongen|\bportret|\bdanser|\bbruid|"
             r"\bweefster|\bweefgetouw|\bwordt\b|\bkuilen\b|\bwoman\b|\bwomen\b|\bpeople\b|\bportrait\b|"
             r"\bdancer|\bhouse\b|\bmarket\b|\bloom\b|\bweaver|\bwearing\b|\bmuseum simalungun\b|\bfoto\b|"
             r"\berepoort|\bbegrafenis|\bgallery\b|\bshop\b|\btari\b|\bmemperkenalkan|\bmelestarikan|"
             r"\bilustrasi|\baesan\b|\bgadis\b|\blimboto\b|\bzainal\b")
TEXTILE_WORDS = r"weefsel|kain|sarong|sarung|selendang|doek|textile|cloth|ikat|songket|tapis|ulos|hinggi|\blau\b|tampan|palepai|geringsing|gringsing|endek|shawl|skirt"


def wiki_thumb(url: str, width: int = 960) -> str | None:
    """Wikimedia's own resized JPEG for an upload URL (TIFF masters are ~10 MB).

    Only Wikimedia's standard thumbnail steps are served (800 px now answers HTTP 400; 960 px works).
    """
    m = re.match(r"https://upload\.wikimedia\.org/wikipedia/commons/([0-9a-f])/([0-9a-f]{2})/(.+)$", url)
    if not m:
        return None
    a, ab, name = m.groups()
    base = f"https://upload.wikimedia.org/wikipedia/commons/thumb/{a}/{ab}/{name}"
    if name.lower().endswith((".tif", ".tiff")):
        return f"{base}/lossy-page1-{width}px-{name}.jpg"
    return f"{base}/{width}px-{name}"


def openverse() -> list[dict]:
    found, seen = [], set()
    for q in OPENVERSE_QUERIES:
        for page in (1, 2, 3):
            url = (f"https://api.openverse.org/v1/images/?q={urllib.parse.quote(q)}&page_size=20&page={page}"
                   "&license_type=commercial")
            try:
                data = get_json(url) or {}
            except ValueError as exc:
                print("openverse failed:", q, exc)
                break
            results = data.get("results") or []
            for r in results:
                title = r.get("title") or ""
                if r["id"] in seen or not re.search(TEXTILE_WORDS, title.lower()) or re.search(NOT_CLOTH, title.lower()):
                    continue
                seen.add(r["id"])
                label = label_of(title)
                if label:
                    found.append({"source": "Openverse/" + (r.get("source") or "?"), "id": f"ov-{r['id']}",
                                  "label": label, "title": title, "place": title[:200],
                                  "image": wiki_thumb(r.get("url") or "") or r.get("url"),
                                  "fallback": [r.get("url"), f"https://api.openverse.org/v1/images/{r['id']}/thumb/"],
                                  "url": r.get("foreign_landing_url"),
                                  "license": f"{(r.get('license') or '').upper()} {r.get('license_version') or ''}".strip(),
                                  "creator": r.get("creator")})
            time.sleep(1.0)
            if page >= (data.get("page_count") or 1):
                break
    return found


def _fetch_image(url: str, path: Path) -> bool:
    """Download, then normalise to an RGB JPEG of at most 1024 px; False if it is not an image."""
    from PIL import Image

    tmp = path.with_suffix(".part")
    subprocess.run(["curl", "-sL", "--max-time", "90", "-o", str(tmp), url], check=False)
    try:
        img = Image.open(tmp)
        img.thumbnail((1024, 1024))
        img.convert("RGB").save(path, format="JPEG", quality=88)
        return True
    except Exception:  # noqa: BLE001 - not an image (error page, rate limit, ...)
        return False
    finally:
        tmp.unlink(missing_ok=True)


def download(items: list[dict]) -> list[dict]:
    OUT.mkdir(parents=True, exist_ok=True)
    kept = []
    for it in items:
        path = OUT / f"{it['id']}.jpg"
        ok = path.exists() and path.stat().st_size > 0
        for url in ([it["image"]] + [u for u in it.get("fallback") or [] if u]) if not ok else []:
            if _fetch_image(url, path):
                ok = True
                break
            time.sleep(0.5)
        if ok:
            kept.append({k: v for k, v in it.items() if k != "fallback"} | {"file": path.name})
    return kept


def main() -> None:
    items = met() + openverse()
    kept = download(items)
    (OUT / "manifest.json").write_text(json.dumps(kept, indent=1, ensure_ascii=False))
    keep = {k["file"] for k in kept}
    for stale in OUT.glob("*.jpg"):  # images from earlier runs that no longer pass the filters
        if stale.name not in keep:
            stale.unlink()
    from collections import Counter

    print("found:", len(items), "downloaded:", len(kept))
    print(Counter(k["label"] for k in kept).most_common())
    print(Counter(k["source"] for k in kept))


if __name__ == "__main__":
    main()
