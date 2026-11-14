"use client";

import { useState } from "react";
import Link from "next/link";
import { api, fileUrl } from "@/lib/api";
import type { Entry } from "@/lib/types";
import type { GalleryVariant } from "@/lib/variants";
import { regionExploreHrefForEntry } from "@/lib/regions";
import { Notice, useLoad } from "@/components/ui";

type Passport = { story: { body: string; unresolved: string[] } | null; citations: { source_id: string; title: string; url: string | null }[]; notice: string; review: { is_demo_seed: boolean } };
type Result = { id: string; passport: Passport; variants: GalleryVariant[] };

export function RegionalStories({ entries }: { entries: Entry[] }) {
  const [entryId, setEntryId] = useState(entries[0]?.id ?? "");
  const [tab, setTab] = useState<"kenali" | "cerita" | "motif">("kenali");
  const [chapter, setChapter] = useState(0);
  const data = useLoad(async (): Promise<Result | null> => {
    const entry = entries.find((item) => item.id === entryId);
    if (!entry) return null;
    const [passport, variants] = await Promise.all([
      api<Passport>(`/gallery/${encodeURIComponent(entry.slug)}/passport`, { token: null }),
      api<GalleryVariant[]>(`/gallery/${encodeURIComponent(entry.slug)}/variants`, { token: null }),
    ]);
    return { id: entry.id, passport, variants };
  }, entryId);
  const entry = entries.find((item) => item.id === entryId);
  const content = data.data?.id === entryId ? data.data : null;
  return <div className="grid gap-6">
    <ul className="grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">{entries.map((item) => <li key={item.id} className="grid content-start gap-3 rounded-xl bg-surface p-6"><span className="text-sm uppercase tracking-wider">{item.region ?? "Nusantara"} · {item.technique ?? "Tenun"}</span><h3 className="text-xl font-semibold">{item.name}</h3><p className="text-base">{item.summary}</p><button className="btn btn-quiet w-fit !border !border-current" aria-pressed={entryId === item.id} onClick={() => { setEntryId(item.id); setTab("kenali"); setChapter(0); }}>Jelajahi kain ini</button><Link className="link w-fit text-base" href={regionExploreHrefForEntry(item)}>Jelajahi daerah ini →</Link></li>)}</ul>
    {entry && <section className="grid gap-5 rounded-2xl bg-white/70 p-5 sm:p-8" aria-label={`Penjelajahan ${entry.name}`}><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-sm uppercase tracking-wider">Kain daerah</p><h3 className="t-head mt-2">{entry.name}</h3></div><button className="link text-base" onClick={() => setEntryId("")}>Tutup</button></div>
      <div className="flex flex-wrap gap-2" aria-label="Bagian penjelajahan"><button className={`rounded-full px-4 py-2 ${tab === "kenali" ? "bg-field text-field-ink" : "bg-surface"}`} aria-pressed={tab === "kenali"} onClick={() => setTab("kenali")}>Kenali kain</button><button className={`rounded-full px-4 py-2 ${tab === "cerita" ? "bg-field text-field-ink" : "bg-surface"}`} aria-pressed={tab === "cerita"} onClick={() => setTab("cerita")}>Cerita budaya</button><button className={`rounded-full px-4 py-2 ${tab === "motif" ? "bg-field text-field-ink" : "bg-surface"}`} aria-pressed={tab === "motif"} onClick={() => setTab("motif")}>Pilihan motif</button></div>
      {data.error && <Notice tone="error">{data.error}</Notice>}
      {!content && !data.error && <p role="status">Memuat cerita dan motif…</p>}
      {content && tab === "kenali" && <div className="grid gap-4"><p>{entry.summary}</p><dl className="grid gap-3 text-base sm:grid-cols-2">{([["Jenis", entry.kind], ["Teknik", entry.technique], ["Daerah", entry.region], ["Komunitas", entry.community]] as const).filter(([, value]) => value).map(([label, value]) => <div key={label} className="rounded-lg bg-surface p-4"><dt className="text-sm text-muted">{label}</dt><dd>{value}</dd></div>)}</dl><p className="text-sm text-muted">{content.passport.notice}</p><button className="btn w-fit" onClick={() => setTab("cerita")}>Lanjut ke cerita</button></div>}
      {content && tab === "cerita" && <div className="grid gap-4">{content.passport.story ? (() => { const chapters = content.passport.story.body.split("\n").filter(Boolean); const index = Math.min(chapter, Math.max(0, chapters.length - 1)); return <><p className="text-sm uppercase tracking-wider">Bagian {index + 1} dari {chapters.length}</p><p>{chapters[index]}</p><div className="flex flex-wrap items-center gap-3"><button className="btn btn-quiet" disabled={index === 0} onClick={() => setChapter((value) => Math.max(0, value - 1))}>Sebelumnya</button><button className="btn" disabled={index >= chapters.length - 1} onClick={() => setChapter((value) => Math.min(chapters.length - 1, value + 1))}>Lanjutkan</button></div>{content.passport.story.unresolved.length > 0 && <p className="text-base text-muted">Belum terverifikasi: {content.passport.story.unresolved.join("; ")}</p>}</>; })() : <p>Cerita yang disetujui belum tersedia.</p>}{content.passport.review.is_demo_seed && <p className="text-base">Entri ini menggunakan narasi demo.</p>}{content.passport.citations.length > 0 && <div><p className="font-semibold">Sumber</p><ul className="list-disc pl-5 text-base">{content.passport.citations.map((source, index) => <li key={`${source.source_id}-${index}`}>{source.url ? <a className="link" href={source.url} target="_blank" rel="noreferrer">{source.title}</a> : source.title}</li>)}</ul></div>}<p className="text-sm text-muted">{content.passport.notice}</p><button className="btn w-fit" onClick={() => setTab("motif")}>Lanjut ke motif</button><Link href={regionExploreHrefForEntry(entry)} className="link w-fit">Jelajahi daerah ini</Link></div>}
      {content && tab === "motif" && <div className="grid gap-4"><p className="text-base">Gambar berikut adalah referensi varian; foto barang tersedia pada masing-masing penawaran.</p>{content.variants.length ? <ul className="grid list-none gap-4 p-0 sm:grid-cols-2">{content.variants.map((variant) => <li key={variant.id} className="grid content-start gap-3 rounded-xl bg-surface p-4">{variant.images[0] && <img src={fileUrl(variant.images[0].url)} alt={variant.images[0].caption ?? `Referensi ${variant.name}`} className="aspect-[4/3] w-full rounded-lg object-cover" />}<h4 className="font-semibold">{variant.name}</h4>{variant.description && <p className="text-base">{variant.description}</p>}<Link className="btn btn-quiet w-fit !border !border-current" href={`/gallery/${entry.slug}/study?variant=${encodeURIComponent(variant.id)}`}>Amati motif</Link><Link className="link w-fit text-base" href={`/gallery/${entry.slug}?variant=${encodeURIComponent(variant.id)}#listings`}>Lihat penawaran</Link></li>)}</ul> : <p>Belum ada varian motif yang tersedia.</p>}</div>}
    </section>}
  </div>;
}
