#!/usr/bin/env python3
"""Offline (no API cost) evaluation of photo-to-photo retrieval for tradition identification.

Labelled images: Sikka v3 (432 photos, 24 motif classes), NTT 534 originals (Sumba, Flores,
Manggarai) and Bali 336 originals (songket, endek, gringsing, wali). Only non-augmented originals.

Protocol (leave-one-group-out, so a photo is never matched against the same cloth/motif):
  - NTT and Bali: group = motif name from the dataset metadata.
  - Sikka: group = motif class (a whole class is held out at once).
Scoring per tradition = mean of the top-M cosine similarities among that tradition's references,
so a large class (Sikka) cannot win by count alone. Reports per-tradition recall, macro recall,
and precision/coverage when abstaining below a margin between the best and second-best tradition.

Run from services/api:  uv run python ../../experiments/vlm_eval/image_knn_eval.py
"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/tenun_datasets"
CACHE = ROOT / "experiments/vlm_eval/results"
MODELS = ["google/siglip2-base-patch16-224", "Qdrant/clip-ViT-B-32-vision", "nomic-ai/nomic-embed-vision-v1.5",
          "jinaai/jina-clip-v1"]


def bali_label(jenis: str) -> str | None:
    j = " ".join(jenis.split()).lower()
    if "songket" in j:
        return "Songket Bali"
    if "endek" in j:
        return "Endek Bali"
    if "gringsing" in j:
        return "Gringsing Tenganan"
    if "wali" in j:
        return "Tenun Wali/Wewali"
    return None  # e.g. a single 'bebali' cloth: too few to evaluate


def ntt_label(kab: str) -> str:
    k = kab.lower()
    if k.startswith("sumba"):
        return "Tenun Ikat Sumba"
    if "manggarai" in k:
        return "Songke Manggarai"
    return "Flores (lainnya)"


def dataset(museum: bool = False, commons: bool = False) -> list[dict]:
    items = []
    for x in json.loads((DATA / "mendeley_ntt_534/534 NTT motifs.json").read_text()):
        p = DATA / "mendeley_ntt_534/originals" / x["file_original"].split("/")[-1]
        if p.exists():
            items.append({"path": p, "label": ntt_label(x["kabupaten_kota"]), "group": "ntt:" + x["motif_name"],
                          "source": "mendeley-ntt"})
    for x in json.loads((DATA / "mendeley_bali_336/336 bali motifs.json").read_text()):
        p = DATA / "mendeley_bali_336/originals" / x["file_original"].split("/")[-1]
        label = bali_label(x["jenis"])
        if p.exists() and label:
            items.append({"path": p, "label": label, "group": "bali:" + x["motif_name"], "source": "mendeley-bali"})
    for cls in sorted((DATA / "mendeley_sikka_v3/extracted/sikka_motif_512").iterdir()):
        if cls.is_dir():
            for p in sorted(cls.glob("*.jpg")):
                items.append({"path": p, "label": "Tenun Ikat Sikka", "group": "sikka:" + cls.name,
                              "source": "mendeley-sikka"})
    manifest = DATA / "museum/manifest.json"
    if museum and manifest.exists():
        for m in json.loads(manifest.read_text()):
            items.append({"path": DATA / "museum" / m["file"], "label": m["label"], "group": m["id"],
                          "source": m["source"]})
    manifest = DATA / "commons/manifest.json"  # fetch_commons.py; source = group = uploader
    if commons and manifest.exists():
        for m in json.loads(manifest.read_text()):
            items.append({"path": DATA / "commons" / m["file"], "label": m["label"], "group": m["id"],
                          "source": m["source"]})
    return items


CROPS = [(0.5, 0.5), (0.3, 0.3), (0.7, 0.3), (0.3, 0.7), (0.7, 0.7)]


def crop_files(paths: list[Path], workdir: Path) -> tuple[list[str], list[int]]:
    """Five half-size crops per photo, so the motif counts more than background and framing."""
    from PIL import Image, ImageOps

    workdir.mkdir(parents=True, exist_ok=True)
    files, owner = [], []
    for i, p in enumerate(paths):
        img = ImageOps.autocontrast(Image.open(p).convert("RGB"))
        w, h = img.size
        side = int(min(w, h) * 0.5)
        for j, (cx, cy) in enumerate(CROPS):
            x, y = max(0, int(cx * w - side / 2)), max(0, int(cy * h - side / 2))
            f = workdir / f"{i}_{j}.jpg"
            if not f.exists():
                img.crop((x, y, x + side, y + side)).save(f, quality=90)
            files.append(str(f))
            owner.append(i)
    return files, owner


# models without a fastembed build: Hugging Face repo -> (vision ONNX file, input size, mean, std)
ONNX_MODELS = {"Marqo/marqo-fashionSigLIP": ("onnx/vision_model.onnx", 224, 0.5, 0.5)}


def _onnx_encoder(model: str):
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download
    from PIL import Image

    file, side, mean, std = ONNX_MODELS[model]
    sess = ort.InferenceSession(hf_hub_download(model, file), providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name

    class Enc:
        def embed(self, files, batch_size=16):
            for k in range(0, len(files), batch_size):
                batch = np.stack([(np.asarray(Image.open(f).convert("RGB").resize((side, side), Image.BICUBIC),
                                              dtype=np.float32) / 255.0 - mean) / std for f in files[k:k + batch_size]])
                yield from sess.run(None, {name: batch.transpose(0, 3, 1, 2)})[0]

    return Enc()


def embed(model: str, paths: list[Path], crops: bool = False) -> np.ndarray:
    tag = "crops" if crops else "full"
    key = int(hashlib.sha1("\n".join(str(p) for p in paths).encode()).hexdigest(), 16) % 10**8  # stable across runs
    cache = CACHE / f"emb_{model.replace('/', '_')}_{tag}_{len(paths)}_{key}.npy"
    if cache.exists():
        return np.load(cache)
    if model in ONNX_MODELS:
        enc = _onnx_encoder(model)
    else:
        from fastembed import ImageEmbedding

        enc = ImageEmbedding(model)
    if crops:
        files, owner = crop_files(paths, CACHE / f"crops_{len(paths)}_{key}")
        raw = np.array(list(enc.embed(files, batch_size=16)), dtype=np.float32)
        raw /= np.linalg.norm(raw, axis=1, keepdims=True)
        vecs = np.zeros((len(paths), raw.shape[1]), dtype=np.float32)
        for k, i in enumerate(owner):
            vecs[i] += raw[k]
    else:
        vecs = np.array(list(enc.embed([str(p) for p in paths], batch_size=16)), dtype=np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(cache, vecs)
    return vecs


DATASET_SOURCES = {"mendeley-ntt", "mendeley-bali", "mendeley-sikka"}
NEAR_DUP = 0.95  # the same object can arrive twice (The Met directly and via Openverse)


def evaluate(items, vecs, top_m: int, cap: int | None = None, cross_source: bool = False,
             query_sources: set | None = None, ref_sources: set | None = None) -> list[dict]:
    import random

    labels = np.array([i["label"] for i in items])
    groups = np.array([i["group"] for i in items])
    sources = np.array([i.get("source", "") for i in items])
    classes = sorted(set(labels))
    sims = vecs @ vecs.T
    keep = np.ones(len(items), bool)
    if cap:  # at most `cap` references per (tradition, source), fixed seed
        rng = random.Random(0)
        by = defaultdict(list)
        for k in range(len(items)):
            by[(labels[k], sources[k])].append(k)
        keep[:] = False
        for idx in by.values():
            for k in rng.sample(idx, min(cap, len(idx))):
                keep[k] = True
    out = []
    for i in range(len(items)):
        if query_sources and sources[i] not in query_sources:
            continue
        allowed = keep & (groups != groups[i]) & (sims[i] < NEAR_DUP)
        if ref_sources is not None:
            allowed &= np.isin(sources, list(ref_sources))
        if cross_source:
            allowed &= sources != sources[i]
        scores = {}
        for c in classes:
            s = np.sort(sims[i][allowed & (labels == c)])[::-1][:top_m]
            if len(s):
                scores[c] = float(s.mean())
        if not scores:
            continue
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        margin = ranked[0][1] - (ranked[1][1] if len(ranked) > 1 else 0.0)
        out.append({"label": labels[i], "pred": ranked[0][0], "margin": margin,
                    "top3": [c for c, _ in ranked[:3]]})
    return out


def report(model, res, items) -> dict:
    per = defaultdict(lambda: [0, 0])
    for r in res:
        per[r["label"]][1] += 1
        per[r["label"]][0] += r["pred"] == r["label"]
    macro = np.mean([ok / n for ok, n in per.values()])
    top3 = np.mean([r["label"] in r["top3"] for r in res])
    print(f"\n### {model}")
    for c, (ok, n) in sorted(per.items(), key=lambda kv: -kv[1][1]):
        print(f"  {c:22s} {ok:3d}/{n:<3d}  {ok / n:5.0%}")
    print(f"  macro recall {macro:.0%}   overall {np.mean([r['pred'] == r['label'] for r in res]):.0%}   "
          f"benar di top-3 {top3:.0%}")
    # abstain when the best tradition does not beat the runner-up by enough
    for t in (0.0, 0.01, 0.02, 0.03, 0.05):
        kept = [r for r in res if r["margin"] >= t]
        if kept:
            prec = np.mean([r["pred"] == r["label"] for r in kept])
            print(f"    margin>={t:.2f}: dijawab {len(kept) / len(res):4.0%}  benar dari yang dijawab {prec:4.0%}")
    return {"model": model, "macro": float(macro)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=MODELS)
    ap.add_argument("--top-m", type=int, default=3)
    ap.add_argument("--museum", action="store_true", help="add the museum photos (fetch_museum.py)")
    ap.add_argument("--crops", action="store_true", help="embed five motif crops per photo")
    ap.add_argument("--commons", action="store_true", help="add the Wikimedia Commons photos (fetch_commons.py)")
    ap.add_argument("--cap", type=int, default=None, help="max references per tradition and source")
    ap.add_argument("--cross-source", action="store_true", help="references must come from another source")
    ap.add_argument("--queries", choices=["all", "museum", "commons", "datasets"], default="all",
                    help="which photos are tested")
    ap.add_argument("--refs", choices=["all", "datasets"], default="all",
                    help="'datasets' = Mendeley only, to see what the museum references add")
    a = ap.parse_args()
    items = dataset(museum=a.museum, commons=a.commons)
    print("images:", len(items), dict(Counter(i["label"] for i in items)))
    print("sources:", dict(Counter(i["source"] for i in items)), "groups:", len({i["group"] for i in items}))
    summary = []
    for m in a.models:
        vecs = embed(m, [i["path"] for i in items], crops=a.crops)
        all_sources = {i["source"] for i in items}
        res = evaluate(items, vecs, a.top_m, cap=a.cap, cross_source=a.cross_source,
                       query_sources={"all": None, "datasets": DATASET_SOURCES,
                                      "commons": {s for s in all_sources if s.startswith("commons/")},
                                      "museum": {s for s in all_sources - DATASET_SOURCES
                                                 if not s.startswith("commons/")}}[a.queries],
                       ref_sources=DATASET_SOURCES if a.refs == "datasets" else None)
        summary.append(report(m, res, items))
    print("\nringkas:", sorted(((round(s["macro"], 3), s["model"]) for s in summary), reverse=True))


if __name__ == "__main__":
    main()
