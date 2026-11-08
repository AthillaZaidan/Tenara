#!/usr/bin/env python3
"""Does a VLM pick the right tradition when it SEES reference photos of the top candidates?

Photo-to-photo retrieval (SigLIP 2, five motif crops per photo) often has the right tradition at rank
2-3. Here the model gets the query photo plus the two nearest reference photos of each of the top-K
traditions, and picks one (or none). Accuracy is compared against retrieval top-1 on the same queries.

Queries are museum/archive photos (fetch_museum.py). References are every other labelled photo,
excluding the same object (group), near-duplicates and the query's own source. Candidate order is shuffled with a fixed seed so
position bias cannot help. Spend is capped by --budget using OpenRouter's billed `usage.cost`.

Run from services/api (OPENROUTER_API_KEY in the repo-root .env):
    uv run python ../../experiments/vlm_eval/visual_rerank_eval.py --limit 20 --budget 0.05
"""
import argparse
import base64
import io
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "services" / "api"))

import image_knn_eval as knn

from app.core.config import settings
from app.ml import llm_client

MODEL = "google/siglip2-base-patch16-224"
SYSTEM = (
    "Anda ahli tekstil tradisional Indonesia. Bandingkan foto KUERI dengan foto referensi tiap kandidat. "
    "Nilai teknik (ikat lungsin, ikat pakan, ikat ganda, songket/benang emas, sulam/tapis), struktur tata letak "
    "(bidang, garis tepi, pola berulang), bentuk motif, dan palet warna. Abaikan pencahayaan, latar, dan cara "
    "foto diambil. Pilih kandidat yang paling cocok, atau 'none' jika tidak ada yang meyakinkan. "
    'Jawab JSON saja: {"choice": "A"|"B"|"C"|...|"none", "reason": "<= 30 kata"}'
)


def small(path: Path, side: int = 448) -> dict:
    from PIL import Image

    img = Image.open(path).convert("RGB")
    img.thumbnail((side, side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()}}


def shortlist(i, sims, labels, groups, sources, top_m=3, k=3, per=2):
    # strict: references from another source only, so a collection's photo style cannot give the answer
    allowed = (groups != groups[i]) & (sims[i] < knn.NEAR_DUP) & (sources != sources[i])
    scored = []
    for c in sorted(set(labels)):
        idx = np.where(allowed & (labels == c))[0]
        if len(idx):
            order = idx[np.argsort(-sims[i][idx])]
            scored.append((float(sims[i][order[:top_m]].mean()), c, order[:per].tolist()))
    scored.sort(reverse=True)
    return scored[:k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vlm", default="google/gemma-4-26b-a4b-it")
    ap.add_argument("--limit", type=int, default=20, help="number of museum queries (spread over traditions)")
    ap.add_argument("--k", type=int, default=3, help="candidate traditions shown")
    ap.add_argument("--budget", type=float, default=0.05, help="USD cap")
    a = ap.parse_args()

    items = knn.dataset(museum=True)
    vecs = knn.embed(MODEL, [i["path"] for i in items], crops=True)
    sims = vecs @ vecs.T
    labels = np.array([i["label"] for i in items])
    groups = np.array([i["group"] for i in items])
    sources = np.array([i["source"] for i in items])
    queries = [i for i, it in enumerate(items) if it["source"] not in knn.DATASET_SOURCES]

    # round-robin over traditions, so one big class does not fill the sample
    rng = random.Random(0)
    by = defaultdict(list)
    for i in queries:
        by[labels[i]].append(i)
    for v in by.values():
        rng.shuffle(v)
    picked = []
    while len(picked) < a.limit and any(by.values()):
        for c in sorted(by):
            if by[c] and len(picked) < a.limit:
                picked.append(by[c].pop())

    settings.llm_provider = "openrouter"
    spent, rows = 0.0, []
    out = HERE / "results" / f"rerank-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as live:
        for i in picked:
            if spent >= a.budget:
                print(f"budget ${a.budget} reached (${spent:.4f}); stopping")
                break
            cands = shortlist(i, sims, labels, groups, sources, k=a.k)
            shown = cands[:]
            rng.shuffle(shown)
            letters = [chr(65 + n) for n in range(len(shown))]
            content = [{"type": "text", "text": "Foto KUERI:"}, small(items[i]["path"])]
            for letter, (_, c, refs) in zip(letters, shown, strict=True):
                content.append({"type": "text", "text": f"Kandidat {letter}: {c} (foto referensi):"})
                content += [small(items[r]["path"]) for r in refs]
            row = {"query": items[i]["group"], "label": labels[i], "knn_top1": cands[0][1],
                   "in_shortlist": labels[i] in [c for _, c, _ in cands], "choice": None, "error": None}
            try:
                res = llm_client.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}],
                                      model=a.vlm)
                cost = float((res.usage or {}).get("cost") or 0)
                spent += cost
                ans = llm_client.parse_json(res.content, "rerank")
                pick = str(ans.get("choice", "none")).strip().upper()[:1]
                row.update(cost=cost, reason=ans.get("reason"),
                           choice=dict(zip(letters, [c for _, c, _ in shown], strict=True)).get(pick, "none"))
            except RuntimeError as exc:
                row["error"] = str(exc)[:200]
            rows.append(row)
            live.write(json.dumps(row, ensure_ascii=False) + "\n")
            live.flush()
            print(f"{row['label'][:28]:28s} knn={row['knn_top1'][:22]:22s} vlm={str(row['choice'])[:22]:22s} "
                  f"${row.get('cost', 0):.5f} err={row['error']}", flush=True)

    done = [r for r in rows if not r["error"]]
    if not done:
        return
    n = len(done)
    print(f"\n{n} kueri, biaya ${spent:.4f} (rata-rata ${spent / n:.5f}/kueri), hasil: {out}")
    print(f"  retrieval top-1 benar : {sum(r['knn_top1'] == r['label'] for r in done)}/{n}")
    print(f"  VLM memilih benar     : {sum(r['choice'] == r['label'] for r in done)}/{n}")
    print(f"  VLM menjawab 'none'   : {sum(r['choice'] == 'none' for r in done)}/{n}")
    print(f"  jawaban ada di kandidat (batas atas): {sum(r['in_shortlist'] for r in done)}/{n}")


if __name__ == "__main__":
    main()
