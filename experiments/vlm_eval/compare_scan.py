#!/usr/bin/env python3
"""Compare vision models on the real fabric-scan pipeline (describe -> web search -> judge).

Runs the production code in services/api/app/ml/vision/vlm.py once per model, with each model doing
all three steps, and records the cost OpenRouter bills for every call (`usage.cost`, which includes
the web-plugin fee on search calls). Spend is also cross-checked against the key's usage before/after.

Run from services/api (needs the app package, Postgres for Gallery names, and OPENROUTER_API_KEY in
the repo-root .env):
    uv run python ../../experiments/vlm_eval/compare_scan.py --budget 2
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.base import SessionLocal  # noqa: E402
from app.ml import llm_client  # noqa: E402
from app.ml.vision import vlm  # noqa: E402
from app.models import GalleryEntry  # noqa: E402

SIKKA = ROOT / "data/tenun_datasets/mendeley_sikka_v3/extracted/sikka_motif_512"
IMG = ROOT / "web/public/img"
# Known origins: Sikka photos are GI-registered Sikka ikat motifs; KITLV titles say "uit Soemba";
# the songket is catalogued as Palembang. Region counts as right if any keyword appears.
CASES = [
    ("sikka_naga_lalan", SIKKA / "naga_lalan/nagalalan_indoor_morning_007_png.rf.ebcd3e7134b1656e52d687797d05fb19.jpg",
     "ikat", ["sikka", "maumere", "flores"]),
    ("sikka_merak", SIKKA / "merak/merak_outdoor_morning_164_png.rf.9be658daa3c707fb11c25e05ceb34726.jpg",
     "ikat", ["sikka", "maumere", "flores"]),
    ("sumba_kitlv_5636", IMG / "ikat-1.jpg", "ikat", ["sumba"]),
    ("sumba_laoe_komboe", IMG / "ikat-3.jpg", "ikat", ["sumba"]),
    ("songket_palembang", IMG / "songket.jpg", "songket", ["palembang", "sumatera selatan", "south sumatra"]),
]
DEFAULT_MODELS = ["google/gemma-4-31b-it", "google/gemma-4-26b-a4b-it", "xiaomi/mimo-v2.6-flash",
                  "openai/gpt-6-luna"]


def key_usage() -> float | None:
    req = urllib.request.Request("https://openrouter.ai/api/v1/key",
                                 headers={"Authorization": f"Bearer {settings.openrouter_api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return float(json.load(r)["data"]["usage"])
    except Exception:  # noqa: BLE001 - reporting only
        return None


CALLS: list[dict] = []
STATE = {"model": None, "case": None, "step": None}
_real_chat = llm_client.chat


def recording_chat(messages, **kw):
    t0 = time.time()
    rec = {**STATE, "seconds": None, "cost": 0.0, "prompt_tokens": 0, "completion_tokens": 0, "error": None}
    try:
        out = _real_chat(messages, **kw)
        u = out.usage or {}
        rec.update(cost=float(u.get("cost") or 0), prompt_tokens=u.get("prompt_tokens") or 0,
                   completion_tokens=u.get("completion_tokens") or 0)
        return out
    except RuntimeError as exc:
        rec["error"] = str(exc)[:200]
        raise
    finally:
        rec["seconds"] = round(time.time() - t0, 1)
        CALLS.append(rec)


def run(models: list[str], queries: int, budget: float, out_dir: Path) -> None:
    llm_client.chat = recording_chat  # the pipeline calls llm_client.chat; we only observe it
    settings.llm_provider = "openrouter"
    with SessionLocal() as s:
        candidates = [n for (n,) in s.execute(select(GalleryEntry.name).where(GalleryEntry.status == "published"))]
    before = key_usage()
    results = []
    for model in models:
        settings.llm_model = settings.llm_search_model = model
        client = vlm.OpenAICompatVLM()
        for case, path, tech, keywords in CASES:
            spent = sum(c["cost"] for c in CALLS)
            if spent >= budget:
                print(f"budget ${budget} reached (${spent:.4f}); stopping")
                break
            STATE.update(model=model, case=case)
            image, ctype = vlm.shrink(path.read_bytes(), "image/jpeg")
            row = {"model": model, "case": case, "expected_technique": tech, "error": None}
            try:
                STATE["step"] = "describe"
                obs = vlm.normalize_observation(client.describe(image, ctype))
                STATE["step"] = "search"
                try:
                    evidence = vlm.clean_evidence(client.search(obs["search_queries"][:queries]))
                except RuntimeError as exc:
                    evidence, row["search_error"] = [], str(exc)[:200]
                public = {k: v for k, v in obs.items() if k != "search_queries"}
                sources = [{k: e[k] for k in ("id", "domain", "title", "excerpt", "tradition", "region",
                                              "motif_notes")} for e in evidence]
                STATE["step"] = "judge"
                judgment = (vlm.normalize_judgment(client.judge(image, ctype, public, sources, candidates),
                                                   evidence, candidates)
                            if evidence else vlm.normalize_judgment({}, [], candidates))
                said = " ".join(filter(None, [judgment["tradition"], judgment["region"]])).lower()
                row.update(technique=obs["technique"], queries=obs["search_queries"][:queries],
                           evidence=[(e["domain"], e["tier"]) for e in evidence], verdict=judgment["verdict"],
                           tradition=judgment["tradition"], region=judgment["region"],
                           confidence=judgment["confidence"], reason=judgment["reason"],
                           technique_ok=obs["technique"] == tech,
                           region_ok=any(k in said for k in keywords) if said else None)
            except RuntimeError as exc:
                row["error"] = str(exc)[:200]
            results.append(row)
            print(f"{model:28s} {case:20s} tech={row.get('technique')} verdict={row.get('verdict')} "
                  f"said={row.get('tradition')}/{row.get('region')} ok={row.get('region_ok')} err={row['error']}")
    after = key_usage()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (out_dir / f"compare-{stamp}.json").write_text(json.dumps(
        {"calls": CALLS, "results": results, "key_usage_before": before, "key_usage_after": after},
        indent=1, ensure_ascii=False))
    summary(models, results, before, after)


def summary(models, results, before, after) -> None:
    print("\n=== per model ===")
    for m in models:
        rows = [r for r in results if r["model"] == m]
        calls = [c for c in CALLS if c["model"] == m]
        if not rows:
            continue
        n = len(rows)

        def avg(step):
            xs = [c["cost"] for c in calls if c["step"] == step]
            return (sum(xs) / len(xs)) if xs else 0.0

        scan_costs = {}
        for c in calls:
            scan_costs[c["case"]] = scan_costs.get(c["case"], 0) + c["cost"]
        secs = {}
        for c in calls:
            secs[c["case"]] = secs.get(c["case"], 0) + (c["seconds"] or 0)
        print(f"\n{m}")
        print(f"  teknik benar      : {sum(1 for r in rows if r.get('technique_ok'))}/{n}")
        print(f"  daerah benar      : {sum(1 for r in rows if r.get('region_ok'))}/{n}"
              f"   salah: {sum(1 for r in rows if r.get('region_ok') is False)}"
              f"   abstain: {sum(1 for r in rows if r.get('verdict') == 'insufficient')}"
              f"   error: {sum(1 for r in rows if r['error'])}")
        print(f"  biaya rata-rata   : deskripsi ${avg('describe'):.5f} | per query search ${avg('search'):.5f}"
              f" | penilaian ${avg('judge'):.5f}")
        print(f"  biaya per scan    : ${sum(scan_costs.values()) / max(len(scan_costs), 1):.5f}"
              f"   waktu per scan: {sum(secs.values()) / max(len(secs), 1):.1f} s")
    total = sum(c["cost"] for c in CALLS)
    print(f"\ntotal biaya tercatat per panggilan: ${total:.4f}")
    if before is not None and after is not None:
        print(f"pemakaian key OpenRouter: ${before:.4f} -> ${after:.4f} (selisih ${after - before:.4f})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    ap.add_argument("--queries", type=int, default=2)
    ap.add_argument("--budget", type=float, default=2.0)
    ap.add_argument("--out", type=Path, default=ROOT / "experiments/vlm_eval/results")
    a = ap.parse_args()
    run(a.models, a.queries, a.budget, a.out)
