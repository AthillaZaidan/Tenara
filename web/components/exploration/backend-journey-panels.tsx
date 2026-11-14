"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, ArrowUpRight, BookOpen, ChevronLeft, ChevronRight, X } from "lucide-react";
import { api, fileUrl } from "@/lib/api";
import type { Entry } from "@/lib/types";
import type { GalleryVariant } from "@/lib/variants";
import type { ExploreRegion } from "@/lib/exploration";
import { entriesForRegion, regionExploreHrefForEntry, regions } from "@/lib/regions";
import { journeyChapters, chapterLabels, type JourneyChapter, type JourneyProgress } from "@/lib/journey";
import { MapButton, MapIcon } from "./map-button";
import { MapDialog } from "./map-dialog";
import { Notice, useLoad } from "@/components/ui";

type Passport = { story: { body: string; unresolved: string[] } | null; citations: { source_id: string; title: string; url: string | null; publisher: string | null }[]; notice: string; review: { is_demo_seed: boolean } };

export function ApiRegionOverview({ region, entries, read, onChapter, onFreeExplore, onCards, fallback }: {
  region: ExploreRegion; entries: Entry[]; read: JourneyChapter[]; onChapter: (chapter: JourneyChapter) => void;
  onFreeExplore: () => void; onCards: () => void; fallback: boolean;
}) {
  const navRegion = regions.find((item) => item.id === region.id);
  const matches = navRegion ? entriesForRegion(entries, navRegion) : [];
  return <aside className="nx-world-overview" aria-label={`Pengantar ${region.name}`}>
    <div className="nx-overview-scroll"><span className="nx-region-tag"><MapIcon name="pin" />{region.province}</span><span className="nx-small-label">Pilih kain untuk mengenal daerah</span><h1>{region.name}</h1><h2>{region.tagline}</h2>
      <p>{matches.length ? `${matches.length} entri Galeri terbit terkait daerah ini. Cerita, teknik, dan motif ditampilkan dari data yang dikurasi.` : "Belum ada entri Galeri terbit yang dipetakan ke daerah ini. Anda tetap dapat menjelajahi diorama."}</p>
      {fallback && <p className="nx-region-prompt">Pilih cerita untuk mulai menjelajah.</p>}
      {matches.length > 0 && <div className="grid gap-2">{matches.slice(0, 3).map((entry) => <Link key={entry.id} className="map-control map-control--text" href={regionExploreHrefForEntry(entry)}><span className="map-control-content"><span className="map-control-label">{entry.name}</span><span className="map-control-trailing"><ArrowUpRight size={15} /></span></span></Link>)}</div>}
      {fallback && <div className="nx-region-fallback-stories" aria-label="Jelajahi cerita yang tersedia">{journeyChapters.map((chapter) => <MapButton key={chapter} onClick={() => onChapter(chapter)} trailing={<ArrowRight size={16} />}>{chapterLabels[chapter]} {read.includes(chapter) ? "· Sudah dibaca" : ""}</MapButton>)}</div>}
    </div>
    <div className="nx-overview-actions"><MapButton className="nx-overview-primary" trailing={<ArrowRight size={17} />} onClick={onFreeExplore}>Jelajahi diorama</MapButton><MapButton icon={<BookOpen size={16} />} onClick={onCards}>Kain daerah ini</MapButton></div>
  </aside>;
}

export function ApiRegionStoryPanel({ region, chapter, entries, onChapter, onClose, onCards, motifCardsOpen = false }: {
  region: ExploreRegion; chapter: JourneyChapter; entries: Entry[]; onChapter: (chapter: JourneyChapter) => void;
  onClose: () => void; onCards: () => void; motifCardsOpen?: boolean;
}) {
  const index = journeyChapters.indexOf(chapter);
  const next = journeyChapters[(index + 1) % journeyChapters.length];
  const navRegion = regions.find((item) => item.id === region.id);
  const candidates = navRegion ? entriesForRegion(entries, navRegion) : [];
  const [entryId, setEntryId] = useState(candidates[0]?.id ?? "");
  const selected = candidates.find((entry) => entry.id === entryId) ?? candidates[0];
  const passport = useLoad(() => selected ? api<Passport>(`/gallery/${encodeURIComponent(selected.slug)}/passport`, { token: null }) : Promise.resolve(null), selected?.id ?? "none");
  const variants = useLoad(() => selected ? api<GalleryVariant[]>(`/gallery/${encodeURIComponent(selected.slug)}/variants`, { token: null }) : Promise.resolve([]), `${selected?.id ?? "none"}-${chapter}`);
  const title = useRef<HTMLHeadingElement>(null);
  const story = passport.data?.story;
  const paragraphs = story?.body.split("\n").filter(Boolean) ?? [];
  const paragraph = chapter === "culture" ? paragraphs[0] : chapter === "weaving" ? paragraphs[1] : paragraphs[2];
  useEffect(() => { title.current?.focus({ preventScroll: true }); }, [chapter, entryId]);
  return <aside className="nx-region-panel nx-topic-panel" role="dialog" aria-modal="false" aria-labelledby="nx-topic-title" aria-hidden={motifCardsOpen || undefined} inert={motifCardsOpen}>
    <div className="nx-topic-header"><span className="nx-topic-emblem"><BookOpen size={27} /></span><MapButton className="nx-topic-close" trailing={<MapIcon name="close" />} onClick={onClose}>Tutup</MapButton></div>
    <div className="nx-panel-scroll nx-topic-scroll"><span className="nx-small-label">{region.name} / {chapterLabels[chapter]}</span>
      <div className="nx-story-meter"><span>{selected?.name ?? "Konten Galeri"}</span><span>0{index + 1} / 03</span></div><div className="nx-story-progress">{journeyChapters.map((item, i) => <span key={item} className={i <= index ? "is-active" : ""} />)}</div>
      {candidates.length > 1 && <label className="grid gap-2 text-sm">Entri kain<select className="field" value={selected?.id ?? ""} onChange={(event) => setEntryId(event.target.value)}>{candidates.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select></label>}
      <h2 id="nx-topic-title" ref={title} tabIndex={-1}>{chapter === "culture" ? selected?.name ?? `Budaya ${region.name}` : chapter === "weaving" ? `Teknik ${selected?.technique ?? "tenun"}` : `Kain daerah ${region.name}`}</h2>
      {passport.loading && <p role="status">Memuat cerita terkurasi…</p>}
      {passport.error && <Notice tone="error">{passport.error}</Notice>}
      {!selected && <p>Belum ada entri Galeri yang dikaitkan dengan daerah ini.</p>}
      {selected && chapter === "culture" && <><p className="nx-topic-lead">{selected.summary || "Ringkasan belum tersedia."}</p>{paragraph && <p>{paragraph}</p>}</>}
      {selected && chapter === "weaving" && <><p className="nx-topic-lead">{selected.technique || "Teknik belum dicatat pada entri ini."}</p>{paragraph ? <p>{paragraph}</p> : <p>Penjelasan teknik yang disetujui belum tersedia.</p>}</>}
      {selected && chapter === "textiles" && <><p className="nx-topic-lead">{selected.name}</p><p>{paragraph || "Pilih penawaran untuk melihat foto dan spesifikasi kain dari penjual."}</p>{variants.data?.length ? <ul className="list-none p-0">{variants.data.slice(0, 3).map((variant) => <li key={variant.id} className="mb-2 flex items-center gap-3">{variant.images[0] && <img src={fileUrl(variant.images[0].url)} alt="" className="h-12 w-12 rounded object-cover" />}<span>{variant.name}</span></li>)}</ul> : <p className="text-base">Varian motif belum tersedia.</p>}</>}
      {story?.unresolved.length ? <p className="text-sm text-muted">Belum terverifikasi: {story.unresolved.join("; ")}</p> : null}
      {passport.data?.review.is_demo_seed && <p className="text-sm">Konten demo.</p>}
      {passport.data && <p className="text-xs text-muted">{passport.data.notice}</p>}
      {passport.data?.citations.length ? <details><summary className="cursor-pointer text-sm font-semibold">Sumber dan kutipan ({passport.data.citations.length})</summary><ul className="list-disc pl-5 text-sm">{passport.data.citations.map((citation, i) => <li key={`${citation.source_id}-${i}`}>{citation.url ? <a className="link" href={citation.url} target="_blank" rel="noreferrer">{citation.title}</a> : citation.title}{citation.publisher ? ` · ${citation.publisher}` : ""}</li>)}</ul></details> : null}
      <div className="nx-story-actions">{index > 0 && <button type="button" className="nx-story-back" onClick={() => onChapter(journeyChapters[index - 1])}><ChevronLeft size={16} /> Sebelumnya</button>}{index < journeyChapters.length - 1 ? <MapButton className="nx-story-next" trailing={<ArrowRight size={17} />} onClick={() => onChapter(next)}>Lanjut ke {chapterLabels[next]}</MapButton> : <div className="flex flex-wrap gap-2">{selected && <Link href={`/gallery/${selected.slug}/study`} className="map-control map-control--text"><span className="map-control-content"><span className="map-control-label">Ruang studi kain</span><span className="map-control-trailing"><ArrowUpRight size={15} /></span></span></Link>}<MapButton className="nx-story-next" trailing={<ArrowRight size={17} />} onClick={onCards}>Jelajahi kartu kain</MapButton></div>}</div>
    </div>
    <footer className="nx-topic-footer"><div className="nx-topic-stepper"><button aria-label="Kembali ke diorama" onClick={onClose}><ChevronLeft size={19} /><span>Diorama</span></button><span className="nx-chapter-position">0{index + 1} / 03</span><button aria-label={index === 2 ? "Jelajahi kartu kain" : `Buka ${chapterLabels[next]}`} onClick={index === 2 ? onCards : () => onChapter(next)}><span>{index === 2 ? "Kartu kain" : chapterLabels[next]}</span><ChevronRight size={19} /></button></div></footer>
  </aside>;
}

type MotifOption = { entry: Entry; variant: GalleryVariant };
export function ApiMotifCards({ region, entries, onClose, reducedMotion }: { region: ExploreRegion; entries: Entry[]; onClose: () => void; reducedMotion: boolean }) {
  const [selected, setSelected] = useState("");
  const close = useRef<HTMLButtonElement>(null);
  const options = useLoad(async () => {
    const results = await Promise.all(entries.map(async (entry) => ({ entry, variants: await api<GalleryVariant[]>(`/gallery/${encodeURIComponent(entry.slug)}/variants`, { token: null }) })));
    return results.flatMap(({ entry, variants }) => variants.map((variant) => ({ entry, variant })));
  }, entries.map((entry) => entry.id).join("|"));
  const cards: MotifOption[] = options.data ?? [];
  const activeIndex = cards.findIndex((item) => item.variant.id === selected);
  const index = Math.max(0, activeIndex);
  const active = cards[activeIndex];
  useEffect(() => { close.current?.focus(); }, []);
  const choose = (next: number) => { if (cards.length) setSelected(cards[(next + cards.length) % cards.length].variant.id); };
  return <div className={`nx-motif-overlay${reducedMotion ? " nx-motif-still" : ""}`} role="dialog" aria-modal="true" aria-labelledby="nx-motif-heading" onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); onClose(); } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); choose(index + (event.key === "ArrowRight" ? 1 : -1)); } }}>
    <header className="nx-motif-header"><button ref={close} className="nx-motif-close" onClick={onClose}><ArrowLeft size={16} /> Kembali ke cerita <X size={16} /></button><div className="nx-motif-brand" aria-hidden="true">✧ &nbsp; tenara<span>.</span></div><span className="nx-motif-region">{region.province}</span></header>
    <div className="nx-motif-content"><div className="nx-motif-intro"><span>✦ &nbsp; Koleksi {region.name} &nbsp; ✦</span><h2 id="nx-motif-heading">Pilih <em>sehelai cerita.</em></h2><p>Pilih varian terkurasi, lalu lihat penawaran kain yang benar-benar tersedia.</p></div>
      {options.error && <Notice tone="error">{options.error}</Notice>}
      {options.loading && <p role="status">Memuat varian yang tersedia…</p>}
      {cards.length ? <><div className="nx-motif-rail" aria-label={`Varian kain ${region.name}`}>{cards.map((item, i) => <article className={`nx-motif-card${selected === item.variant.id ? " is-selected" : ""}`} data-tone={i % 4} key={item.variant.id}><button className="nx-motif-card-select" type="button" aria-pressed={selected === item.variant.id} onClick={() => setSelected(item.variant.id)}><span className="nx-motif-card-art">{item.variant.images[0] ? <img src={fileUrl(item.variant.images[0].url)} alt={item.variant.images[0].caption ?? `Referensi ${item.variant.name}`} loading="lazy" /> : <span className="grid h-full place-items-center text-sm">Belum ada gambar referensi</span>}</span><span className="nx-motif-card-copy"><span className="nx-motif-kind">{item.entry.name}</span><strong>{item.variant.name}</strong><span className="nx-motif-story">{item.variant.description || "Varian kain terdaftar di Galeri."}</span></span><span className="nx-motif-origin">Referensi · bukan foto penawaran</span></button></article>)}</div><div className="nx-motif-controls"><button type="button" onClick={() => choose(index - 1)} aria-label="Pilih kartu sebelumnya"><ArrowLeft size={18} /></button><span aria-live="polite">{active ? `${String(activeIndex + 1).padStart(2, "0")} / ${String(cards.length).padStart(2, "0")} · ${active.variant.name}` : `${cards.length} varian · Pilih satu kartu`}</span><button type="button" onClick={() => choose(index + 1)} aria-label="Pilih kartu berikutnya"><ArrowRight size={18} /></button></div>{active ? <Link className="nx-motif-continue" href={`/gallery/${active.entry.slug}?variant=${encodeURIComponent(active.variant.id)}#listings`}>Lihat penawaran varian ini <ArrowUpRight size={16} /></Link> : <button className="nx-motif-continue" disabled>Pilih varian untuk melanjutkan <ArrowUpRight size={16} /></button>}</> : !options.loading && <p className="nx-motif-empty">Varian motif untuk daerah ini belum tersedia.</p>}
      <p className="nx-motif-disclaimer">Gambar merupakan referensi budaya. Foto dan stok barang berasal dari listing merchant.</p>
    </div>
  </div>;
}

export function ApiGalleryDashboard({ entries, progress, onClose }: { entries: Entry[]; progress: JourneyProgress; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => entries.filter((entry) => `${entry.name} ${entry.region ?? ""} ${entry.technique ?? ""}`.toLocaleLowerCase("id").includes(query.toLocaleLowerCase("id"))), [entries, query]);
  return <MapDialog title="Kartu kain Galeri" onClose={onClose}>
    <div id="nx-card-dashboard" className="grid gap-5"><p className="text-base">Kartu diambil dari entri Galeri terbit; buka cerita dan sumber untuk detail kurasi.</p><input className="field" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cari nama, daerah, atau teknik" aria-label="Cari entri Galeri" />
      <ul className="grid list-none gap-3 p-0 sm:grid-cols-2">{filtered.map((entry) => <li key={entry.id} className="grid gap-2 rounded-xl bg-surface p-5"><span className="text-xs uppercase tracking-wider">{entry.region ?? "Nusantara"}</span><strong>{entry.name}</strong><span className="text-sm">{entry.technique ?? "Teknik belum dicatat"}</span><Link className="btn btn-quiet w-fit !border !border-current" href={regionExploreHrefForEntry(entry)}>Jelajahi daerah ini</Link></li>)}</ul>
      {!filtered.length && <p>Tidak ada entri yang cocok.</p>}
      <p className="text-xs text-muted">Progress perjalanan perangkat ini: {Object.values(progress).flat().length} bagian dibuka.</p>
    </div>
  </MapDialog>;
}
