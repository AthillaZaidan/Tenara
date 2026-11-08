#!/usr/bin/env python3
"""Compare vision models on the real fabric-scan pipeline (describe -> pgvector RAG -> writer -> critic).

Runs the production code in services/api/app/ml/vision/vlm.py once per model (each model does the
vision description and the writer/critic steps; retrieval is local and free) and records the cost
OpenRouter bills for every call (`usage.cost`). Spend is also cross-checked against the key's usage
before/after. Needs the catalog loaded AND approved by a curator (scripts.seed_catalog).

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


from app.core.config import settings
from app.db.base import SessionLocal
from app.ml import llm_client
from app.ml.text.embedding import get_embedder
from app.ml.vision import vlm

SIKKA = ROOT / "data/tenun_datasets/mendeley_sikka_v3/extracted/sikka_motif_512"
IMG = ROOT / "web/public/img"
TEST = ROOT / "experiments/vlm_eval/testset/assets"  # downloaded, credited in credits.json, git-ignored
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
    # more Sikka motif classes (GI-registered), and museum pieces with recorded provenance
    ("sikka_dala_mawarani", SIKKA / "dala_mawarani/dalamawarani_outdoor_morning_046_png.rf.20fdf267cbaa3424f63c7851c6021e38.jpg",
     "ikat", ["sikka", "maumere", "flores"]),
    ("sikka_manu_hutu", SIKKA / "manu_hutu/manu_hutu_outdoor_morning_012_png.rf.711707d8df8dd26c9ab531a3781cd371.jpg",
     "ikat", ["sikka", "maumere", "flores"]),
    ("sikka_rempe_sikka", SIKKA / "rempe_sikka/rempe_sikka_outdoor_morning_074_png.rf.89359e0adb6a273d21fcdc8e1c5db538.jpg",
     "ikat", ["sikka", "maumere", "flores"]),
    ("sikka_sese_weor", SIKKA / "sese_weor/sese_weor_outdoor_morning_002_png.rf.a611a3c480cd938ced3dc45efe3e61dc.jpg",
     "ikat", ["sikka", "maumere", "flores"]),
    ("tapis_lampung_met", TEST / "woman-s-ceremonial-skirt-tapis-met-dp145517.jpg", "other", ["lampung", "tapis"]),
    ("geringsing_honolulu", TEST / "geringsing-selendang-from-bali-honolulu-museum-of.jpg", "ikat",
     ["gringsing", "geringsing", "tenganan"]),
    ("kalumpang_kitlv", TEST / "ikatweefsel-afkomsting-uit-galoempang-in-de-toradjalanden.jpg", "ikat",
     ["kalumpang", "sekomandi", "mamuju"]),
    ("timor_heirloom", TEST / "heirloom-ikat-textile-from-timor.jpg", "ikat", ["timor", "amarasi", "insana"]),
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


class _StepTagged:
    """Tags writer vs critic calls so costs can be reported per task."""

    def __init__(self, client):
        self.client, self.name = client, client.name

    def complete(self, system, user, image=None, content_type=None):
        STATE["step"] = "writer" if vlm.WRITER in system else "critic"
        return self.client.complete(system, user, image, content_type)


def run(models: list[str], budget: float, out_dir: Path) -> None:
    llm_client.chat = recording_chat  # the pipeline calls llm_client.chat; we only observe it
    settings.llm_provider = "openrouter"
    embedder = get_embedder()
    session = SessionLocal()
    before = key_usage()
    results = []
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    live = (out_dir / f"compare-{stamp}.jsonl").open("a")  # one line per scan, so a stopped run keeps its data
    for model in models:
        settings.llm_model = model
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
                t0 = time.time()
                obs = vlm.normalize_observation(client.describe(image, ctype))
                candidates = vlm.retrieve(session, embedder, obs)
                STATE["step"] = "writer_critic"
                suggestion, _evidence = vlm.identify(_StepTagged(client), obs, candidates, image=image,
                                                    content_type=ctype)
                said = " ".join(filter(None, [suggestion["tradition"], suggestion["region"]])).lower()
                ranked = [c["tradition"] for c in candidates]
                row.update(seconds=round(time.time() - t0, 1), technique=obs["technique"],
                           shortlist=ranked, verdict=suggestion["verdict"],
                           tradition=suggestion["tradition"], region=suggestion["region"],
                           confidence=suggestion["confidence"], reason=suggestion["reason"],
                           technique_ok=obs["technique"] == tech,
                           in_shortlist=any(any(k in (t or "").lower() for k in keywords) for t in ranked),
                           region_ok=any(k in said for k in keywords) if said else None)
            except RuntimeError as exc:
                row["error"] = str(exc)[:200]
            row["cost"] = round(sum(c["cost"] for c in CALLS if c["model"] == model and c["case"] == case), 6)
            results.append(row)
            live.write(json.dumps(row, ensure_ascii=False) + "\n")
            live.flush()
            print(f"{model:28s} {case:20s} tech={row.get('technique')} verdict={row.get('verdict')} "
                  f"said={row.get('tradition')}/{row.get('region')} ok={row.get('region_ok')} "
                  f"${row['cost']:.5f} {row.get('seconds')}s err={row['error']}", flush=True)
    live.close()
    session.close()
    after = key_usage()
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

        def avg(step, calls=calls):
            xs = [c["cost"] for c in calls if c["step"] == step]
            return (sum(xs) / len(xs)) if xs else 0.0

        scan_costs = {}
        for c in calls:
            scan_costs[c["case"]] = scan_costs.get(c["case"], 0) + c["cost"]
        secs = {r["case"]: r.get("seconds") or 0 for r in rows}
        print(f"\n{m}")
        print(f"  teknik benar      : {sum(1 for r in rows if r.get('technique_ok'))}/{n}"
              f"   tradisi benar ada di daftar kandidat: {sum(1 for r in rows if r.get('in_shortlist'))}/{n}")
        print(f"  daerah benar      : {sum(1 for r in rows if r.get('region_ok'))}/{n}"
              f"   salah: {sum(1 for r in rows if r.get('region_ok') is False)}"
              f"   abstain: {sum(1 for r in rows if r.get('verdict') == 'insufficient')}"
              f"   error: {sum(1 for r in rows if r['error'])}")
        print(f"  biaya rata-rata   : deskripsi ${avg('describe'):.5f} | penulis ${avg('writer'):.5f}"
              f" | kritikus ${avg('critic'):.5f}")
        print(f"  biaya per scan    : ${sum(scan_costs.values()) / max(len(scan_costs), 1):.5f}"
              f"   waktu per scan: {sum(secs.values()) / max(len(secs), 1):.1f} s")
    total = sum(c["cost"] for c in CALLS)
    print(f"\ntotal biaya tercatat per panggilan: ${total:.4f}")
    if before is not None and after is not None:
        print(f"pemakaian key OpenRouter: ${before:.4f} -> ${after:.4f} (selisih ${after - before:.4f})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    ap.add_argument("--budget", type=float, default=2.0)
    ap.add_argument("--out", type=Path, default=ROOT / "experiments/vlm_eval/results")
    a = ap.parse_args()
    run(a.models, a.budget, a.out)
