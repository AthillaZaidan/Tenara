"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Entry } from "@/lib/types";
import { regionExploreHrefForEntry } from "@/lib/regions";

/** The page's one live thing: type a place, a motif or a technique and the Gallery answers. */
export function GallerySearch({ entries }: { entries: Entry[] }) {
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Entry[] | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const seq = useRef(0);
  const searching = q.trim().length >= 2;
  const rows = searching && found ? found : entries;

  useEffect(() => {
    const text = q.trim();
    if (text.length < 2) return;
    const mine = ++seq.current;
    const t = setTimeout(async () => {
      try {
        const res = await api<{ mode: string; results: { entry: Entry }[] }>("/search/semantic", { body: { query: text }, token: null });
        if (mine !== seq.current) return;
        setFound(res.results.map((r) => r.entry));
        setNote(res.results.length ? null : "Belum ada entri Gallery yang cocok. Coba nama daerah atau teknik.");
      } catch {
        if (mine === seq.current) setNote("Pencarian sedang tidak tersedia; daftar lengkap ditampilkan.");
      }
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div>
      <label htmlFor="gallery-q" className="block text-base mb-2">Cari kain</label>
      <input
        id="gallery-q"
        className="field"
        type="search"
        placeholder="Misalnya: ikat Sumba, motif kuda, songket Bali"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        autoComplete="off"
      />
      <p className="mt-3 min-h-6 text-base" role="status" aria-live="polite">{searching ? note : null}</p>
      <ul className="mt-6 grid list-none gap-0 p-0">
        {rows.map((e) => (
          <li key={e.id}>
            <Link href={regionExploreHrefForEntry(e)} className="group grid grid-cols-[1fr_auto] items-baseline gap-x-6 py-[13px] no-underline">
              <span className="text-lg group-hover:underline underline-offset-4">{e.name}</span>
              <span className="text-base text-muted text-right">{e.region ?? "Nusantara"} →</span>
              <span className="col-span-2 text-base text-muted">{e.technique ?? e.textile_type}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
