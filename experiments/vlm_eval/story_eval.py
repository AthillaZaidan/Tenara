#!/usr/bin/env python3
"""Real-model run of the listing story (app/ml/text/product_story.py): time, calls, kept and dropped.

For each tradition a temporary listing is made inside a transaction that is rolled back at the end
(nothing is stored). The scan result is a hand-written observation consistent with the catalog
technique, so this measures the writer, the code gates and the critic, not the vision step. Every
call's latency is recorded, and the cited chunk texts are saved next to each sentence for a manual
faithfulness check.

Run from services/api (OPENROUTER_API_KEY in the repo-root .env):
    uv run python ../../experiments/vlm_eval/story_eval.py --models openai/gpt-6-luna google/gemma-4-26b-a4b-it
"""
import argparse
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "services" / "api"))

from sqlalchemy import select

from app.core.config import settings
from app.db.base import SessionLocal
from app.ml.text import product_story
from app.ml.text.embedding import get_embedder
from app.ml.text.story_gen import OpenAICompatTextLLM
from app.ml.vision.vlm import entry_technique
from app.models import FabricListing, GalleryEntry, MerchantProfile, SourceChunk, User

CASES = [  # tradition, claimed origin, motifs, colours
    ("Tenun Ikat Sumba", "Sumba Timur", ["kuda", "udang"], ["merah", "biru tua", "krem"]),
    ("Tenun Ikat Sikka", "Maumere, Sikka", ["belah ketupat", "bunga"], ["biru tua", "hitam", "cokelat"]),
    ("Songket Palembang", "Palembang", ["bunga tabur", "pucuk rebung"], ["merah", "emas"]),
    ("Tapis Lampung", "Lampung", ["kapal", "sulaman"], ["cokelat", "emas"]),
    ("Ulos Batak Toba", "Samosir", ["garis", "ragi"], ["merah", "hitam", "putih"]),
    ("Gringsing Tenganan", "Tenganan, Karangasem", ["wayang", "bintang"], ["merah", "hitam", "krem"]),
    ("Endek Bali", "Gianyar", ["wajik"], ["biru", "merah"]),
    ("Lurik", "Klaten", ["garis"], ["cokelat", "hitam"]),
]


class TimedLLM(OpenAICompatTextLLM):
    def __init__(self):
        super().__init__()
        self.log = []

    def complete(self, system, user):
        t0 = time.monotonic()
        out = super().complete(system, user)
        self.log.append({"role": "writer" if "PENULIS" in system else "critic",
                         "seconds": round(time.monotonic() - t0, 2)})
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=["openai/gpt-6-luna", "google/gemma-4-26b-a4b-it"])
    a = ap.parse_args()
    settings.llm_provider = "openrouter"
    embedder = get_embedder()
    out = HERE / "results" / f"story-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    rows = []
    with out.open("w") as live:
        for model in a.models:
            settings.llm_model = model
            for name, origin, motifs, colors in CASES:
                session = SessionLocal()
                try:
                    entry = session.scalar(select(GalleryEntry).where(GalleryEntry.name == name))
                    if entry is None:
                        print("no entry", name)
                        continue
                    merchant = session.scalar(select(MerchantProfile).limit(1))
                    user = session.get(User, merchant.user_id)
                    listing = FabricListing(merchant_id=merchant.id, entry_id=entry.id, title=f"Uji {name}",
                                            selling_unit="piece", price_idr=100000, city="Uji", province="Uji",
                                            merchant_claimed_origin=origin, piece_length_cm=200, piece_width_cm=60,
                                            min_quantity=Decimal(1), quantity_increment=Decimal(1))
                    tech = entry_technique(entry) or "other"
                    listing.visual_match = {"technique": tech, "motif_elements": motifs, "dominant_colors": colors,
                                            "technique_check": {"status": "cocok"}}
                    session.add(listing)
                    session.flush()
                    llm = TimedLLM()
                    t0 = time.monotonic()
                    story = product_story.generate(session, user, listing, llm, embedder)
                    total = round(time.monotonic() - t0, 2)
                    culture = story.body.split("\n\n")[1] if "\n\n" in story.body else ""
                    cited = {c["chunk_id"]: session.get(SourceChunk, c["chunk_id"]).text for c in story.citations}
                    row = {"model": model, "tradition": name, "seconds": total, "calls": llm.log,
                           "body": story.body, "culture": culture, "notes": story.notes, "cited_texts": cited}
                except Exception as exc:  # noqa: BLE001 - report and continue
                    row = {"model": model, "tradition": name, "error": str(exc)[:300]}
                finally:
                    session.rollback()
                    session.close()
                rows.append(row)
                live.write(json.dumps(row, ensure_ascii=False) + "\n")
                live.flush()
                calls = "+".join(f"{c['role'][0]}{c['seconds']}" for c in row.get("calls", []))
                print(f"{model.split('/')[1][:16]:16s} {name[:22]:22s} {row.get('seconds', '-')}s [{calls}] "
                      f"notes={row.get('notes')} err={row.get('error')}", flush=True)
    print("hasil:", out)
    for model in a.models:
        secs = [r["seconds"] for r in rows if r["model"] == model and "seconds" in r]
        if secs:
            secs.sort()
            print(f"{model}: median {secs[len(secs) // 2]:.1f}s, max {secs[-1]:.1f}s, "
                  f"<=10s {sum(s <= 10 for s in secs)}/{len(secs)}")


if __name__ == "__main__":
    main()
