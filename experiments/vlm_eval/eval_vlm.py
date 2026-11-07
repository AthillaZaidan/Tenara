#!/usr/bin/env python3
"""Evaluate a vision-language model on the Sikka ikat photos (Mendeley, CC BY 4.0).

Setup (you only fill the environment variables):
    LLM_PROVIDER     openai (default) | openrouter | ollama
    OPENAI_API_KEY / OPENROUTER_API_KEY   key for the chosen provider (ollama needs none)
    LLM_MODEL        model id (OPENAI_MODEL still works); e.g. openai/gpt-6-luna on openrouter,
                     gpt-6-luna on openai, qwen3-vl:8b on ollama. Find ids with --list-models
    (keys: env var or a .env file next to this script / in the project root)

Usage:
    python3 eval_vlm.py --list-models
    python3 eval_vlm.py --dry-run                  # no API calls, shows the sample
    python3 eval_vlm.py --per-class 1 --repeat 0   # tiny smoke test (24 calls)
    python3 eval_vlm.py --per-class 5 --repeat 20  # default evaluation

Ground truth caveat: only technique (all Sikka photos are ikat) and the motif class folder are
real labels. CATEGORY_GT below is a provisional guess from class names; a curator must confirm it.
"""
import argparse, base64, json, os, random, re, sys, time, urllib.error, urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
IMG_DIR = ROOT / "data/tenun_datasets/mendeley_sikka_v3/extracted/sikka_motif_512"
OUT_DIR = HERE / "results"
PROVIDERS = {  # LLM_PROVIDER -> (base url, api-key env var or None)
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "ollama": ("http://localhost:11434/v1", None),
}


def provider():
    name = os.environ.get("LLM_PROVIDER", "openai").lower()
    if name not in PROVIDERS:
        sys.exit(f"LLM_PROVIDER must be one of {list(PROVIDERS)}")
    return name


def api_base():
    return PROVIDERS[provider()][0]


def api_headers():
    var = PROVIDERS[provider()][1]
    h = {"Content-Type": "application/json"}
    if var:
        h["Authorization"] = f"Bearer {os.environ[var]}"
    return h


def model_name():
    return os.environ.get("LLM_MODEL") or os.environ.get("OPENAI_MODEL")

# Provisional, confident-only mapping (name-based). Unlisted classes are skipped for category scoring.
CATEGORY_GT = {"burung": "fauna", "merak": "fauna", "naga_lalan": "fauna", "mawar": "flora",
               "manu_ata_bian": "fauna", "manu_dadin": "fauna", "manu_hutu": "fauna", "manu_walu": "fauna"}

TECHNIQUES = ["ikat", "songket", "plain_weave", "printed_or_batik", "other", "unknown"]
CATEGORIES = ["fauna", "flora", "geometric", "figurative", "mixed", "other", "unknown"]


def load_env():
    for p in (HERE / ".env", ROOT / ".env"):
        if p.exists():
            for line in p.read_text().splitlines():
                m = re.match(r"\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\s*$", line)
                if m and not line.lstrip().startswith("#"):
                    os.environ.setdefault(m.group(1), m.group(2).strip().strip("'\""))


def classes():
    return sorted(d.name for d in IMG_DIR.iterdir() if d.is_dir())


def sample(per_class, seed):
    rnd, out = random.Random(seed), []
    for c in classes():
        files = sorted((IMG_DIR / c).glob("*.jpg"))
        out += [(c, f) for f in rnd.sample(files, min(per_class, len(files)))]
    return out


def schema(class_names):
    s = {"type": "object", "additionalProperties": False,
         "required": ["technique", "motif_category", "dominant_colors", "motif_name_top3",
                      "origin_guess", "origin_confidence", "is_traditional_woven_textile"],
         "properties": {
             "is_traditional_woven_textile": {"type": "boolean"},
             "technique": {"type": "string", "enum": TECHNIQUES},
             "motif_category": {"type": "string", "enum": CATEGORIES},
             "dominant_colors": {"type": "array", "items": {"type": "string"}},
             "motif_name_top3": {"type": "array", "items": {"type": "string", "enum": class_names + ["unknown"]}},
             "origin_guess": {"type": ["string", "null"]},
             "origin_confidence": {"type": "string", "enum": ["low", "medium", "high"]}}}
    return {"type": "json_schema", "name": "textile_analysis", "strict": True, "schema": s}


def prompt(class_names):
    return ("You analyse a photo of an Indonesian traditional textile for a marketplace seller. "
            "Describe only what is visible. If unsure, use 'unknown' and low confidence; never guess to please. "
            "Fields: technique; motif_category; dominant_colors (max 3, plain words); "
            "motif_name_top3 = up to 3 best matches from this closed list in order of likelihood, or ['unknown']: "
            + ", ".join(class_names) + "; origin_guess = region/province name or null; "
            "origin_confidence; is_traditional_woven_textile. This is an assistive suggestion that a human will verify.")


def call(model, class_names, path, detail, retries=4):
    b64 = base64.b64encode(path.read_bytes()).decode()
    url = f"data:image/jpeg;base64,{b64}"
    fmt = schema(class_names)
    if provider() == "openai":  # Responses API
        endpoint = f"{api_base()}/responses"
        body = {"model": model, "text": {"format": fmt},
                "input": [{"role": "user", "content": [
                    {"type": "input_text", "text": prompt(class_names)},
                    {"type": "input_image", "image_url": url, "detail": detail}]}]}
    else:  # OpenRouter / Ollama: OpenAI-compatible Chat Completions
        endpoint = f"{api_base()}/chat/completions"
        body = {"model": model, "temperature": 0,
                "response_format": {"type": "json_schema", "json_schema": {
                    "name": fmt["name"], "strict": True, "schema": fmt["schema"]}},
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": prompt(class_names)},
                    {"type": "image_url", "image_url": {"url": url}}]}]}
    req = urllib.request.Request(endpoint, data=json.dumps(body).encode(), method="POST", headers=api_headers())
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                resp = json.load(r)
            if provider() == "openai":
                text = "".join(c.get("text", "") for o in resp.get("output", []) if o.get("type") == "message"
                               for c in o.get("content", []) if c.get("type") == "output_text")
                usage = resp.get("usage", {})
            else:
                text = resp["choices"][0]["message"]["content"]
                u = resp.get("usage", {})
                usage = {"input_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("completion_tokens", 0)}
            return json.loads(text), usage
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:500]
            if e.code in (429, 500, 502, 503) and i < retries - 1:
                time.sleep(2 ** (i + 1)); continue
            raise SystemExit(f"HTTP {e.code}: {msg}")


def list_models():
    req = urllib.request.Request(f"{api_base()}/models", headers=api_headers())
    ids = sorted(m["id"] for m in json.load(urllib.request.urlopen(req, timeout=60))["data"])
    hits = [i for i in ids if "luna" in i.lower()]
    print("Models containing 'luna':", hits or "none found")
    print("All model ids:", ", ".join(ids))


def light(name):
    m = re.search(r"(indoor|outdoor)[_-](morning|noon|night)", name)
    return f"{m.group(1)}_{m.group(2)}" if m else "unknown"


def pct(a, b):
    return f"{100 * a / b:.1f}% ({a}/{b})" if b else "n/a"


def summarize(rows):
    n = len(rows)
    tech = sum(r["pred"]["technique"] == "ikat" for r in rows)
    mapped = [r for r in rows if r["class"] in CATEGORY_GT]
    cat = sum(r["pred"]["motif_category"] == CATEGORY_GT[r["class"]] for r in mapped)
    top1 = sum(r["pred"]["motif_name_top3"][:1] == [r["class"]] for r in rows)
    top3 = sum(r["class"] in r["pred"]["motif_name_top3"][:3] for r in rows)
    unk = sum(r["pred"]["motif_name_top3"][:1] == ["unknown"] for r in rows)
    conf_wrong = sum(r["pred"]["origin_confidence"] == "high" and r["pred"]["motif_name_top3"][:1] != [r["class"]]
                     for r in rows)
    lines = ["# VLM evaluation summary", f"images: {n}", "",
             f"technique == ikat: {pct(tech, n)}",
             f"category correct (provisional GT, {len(mapped)} imgs): {pct(cat, len(mapped))}",
             f"motif name top-1 (24-way zero-shot): {pct(top1, n)}  | chance ~ 4.2%",
             f"motif name top-3: {pct(top3, n)}",
             f"answered 'unknown' as first choice: {pct(unk, n)}",
             f"'high' confidence AND wrong name: {pct(conf_wrong, n)}", "", "## by lighting (top-1 / technique)"]
    by = defaultdict(list)
    for r in rows:
        by[light(r["file"])].append(r)
    for k, v in sorted(by.items()):
        t1 = sum(x["pred"]["motif_name_top3"][:1] == [x["class"]] for x in v)
        te = sum(x["pred"]["technique"] == "ikat" for x in v)
        lines.append(f"- {k}: top-1 {pct(t1, len(v))}, ikat {pct(te, len(v))}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--per-class", type=int, default=5)
    ap.add_argument("--repeat", type=int, default=20, help="re-run N images to measure consistency")
    ap.add_argument("--detail", default="auto", choices=["low", "high", "auto"])
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    load_env()
    cls = classes()
    items = sample(a.per_class, a.seed)
    if a.dry_run:
        print(f"{len(cls)} classes, {len(items)} images selected (+{a.repeat} repeats)")
        for c, f in items[:5]:
            print(" ", c, f.name, light(f.name))
        var = PROVIDERS[provider()][1]
        print("provider:", provider(), "| key set:", bool(var and os.environ.get(var)) if var else "not needed",
              "| model:", model_name())
        return
    var = PROVIDERS[provider()][1]
    if var and not os.environ.get(var):
        sys.exit(f"{var} is not set (env var or .env file).")
    if a.list_models:
        return list_models()
    model = model_name() or sys.exit("LLM_MODEL (or OPENAI_MODEL) is not set. Run --list-models first.")
    OUT_DIR.mkdir(exist_ok=True)
    rows, tokens_in, tokens_out = [], 0, 0
    for i, (c, f) in enumerate(items, 1):
        pred, u = call(model, cls, f, a.detail)
        tokens_in += u.get("input_tokens", 0); tokens_out += u.get("output_tokens", 0)
        rows.append({"class": c, "file": f.name, "pred": pred})
        print(f"[{i}/{len(items)}] {c:18s} -> {pred['motif_name_top3'][:1]} {pred['technique']} {pred['motif_category']}", flush=True)
    same = 0
    rep = random.Random(a.seed + 1).sample(rows, min(a.repeat, len(rows))) if a.repeat else []
    for r in rep:
        pred, u = call(model, cls, IMG_DIR / r["class"] / r["file"], a.detail)
        tokens_in += u.get("input_tokens", 0); tokens_out += u.get("output_tokens", 0)
        same += (pred["technique"], pred["motif_category"], pred["motif_name_top3"][:1]) == \
                (r["pred"]["technique"], r["pred"]["motif_category"], r["pred"]["motif_name_top3"][:1])
    stamp = time.strftime("%Y%m%d_%H%M%S")
    (OUT_DIR / f"raw_{stamp}.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    report = summarize(rows)
    if rep:
        report += f"\n\nconsistency on {len(rep)} repeated images (same technique+category+top1): {pct(same, len(rep))}"
    report += f"\n\nmodel: {model} | tokens in/out: {tokens_in}/{tokens_out}"
    (OUT_DIR / f"summary_{stamp}.md").write_text(report)
    print("\n" + report)


if __name__ == "__main__":
    main()
