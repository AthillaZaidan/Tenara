"use client";

import Link from "next/link";
import { useId, useLayoutEffect, useRef, useState, useSyncExternalStore, type CSSProperties, type ReactNode } from "react";
import {
  ArrowRight,
  ChevronDown,
  ChevronRight,
  Heart,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { fileUrl, idr } from "@/lib/api";
import type { Entry } from "@/lib/types";
import type { CatalogSample } from "@/lib/catalog-data";
import { regionExploreHrefForEntry } from "@/lib/regions";
import { findExploreRegion, type RegionId } from "@/lib/exploration";
import { CatalogImage } from "@/components/CatalogImage";
import "./catalog-browser-motion.css";

type ReferenceImage = { id?: string; url: string; caption: string | null };

export type CatalogRecord = {
  id: string;
  name: string;
  region: string;
  regionId?: RegionId;
  technique: string | null;
  summary: string | null;
  aliases: string[];
  samples: CatalogSample[];
  entry?: Entry;
  reference_images: ReferenceImage[];
  listing_images?: ReferenceImage[];
  availability: { listing_count: number; min_price_idr: number | null };
};

const normalize = (value: string) => value.trim().toLocaleLowerCase("id-ID");
const favoriteKey = "tenara.catalog.favorites";
const favoriteSubscribers = new Set<() => void>();

function savedCatalogIds(): string[] {
  try {
    const value: unknown = JSON.parse(window.localStorage.getItem(favoriteKey) ?? "[]");
    return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
  } catch { return []; }
}

function subscribeFavorites(callback: () => void) {
  favoriteSubscribers.add(callback);
  window.addEventListener("storage", callback);
  return () => {
    favoriteSubscribers.delete(callback);
    window.removeEventListener("storage", callback);
  };
}

const compactFiltersQuery = "(max-width: 900px)";
function subscribeCompactFilters(callback: () => void) {
  const media = window.matchMedia(compactFiltersQuery);
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
}

function CatalogCard({ record, index }: { record: CatalogRecord; index: number }) {
  const [imageIndex, setImageIndex] = useState(0);
  const favorite = useSyncExternalStore(subscribeFavorites, () => savedCatalogIds().includes(record.id), () => false);
  const { entry, availability } = record;
  const sample = record.samples[0];
  const imageSources = sample
    ? [sample.images.utama, sample.images.datar, sample.images.closeup]
    : [...record.reference_images, ...(record.listing_images ?? [])]
        .map((image) => fileUrl(image.url))
        .filter((source, imageIndex, sources) => sources.indexOf(source) === imageIndex)
        .slice(0, 3);
  const image = record.reference_images[0] ?? record.listing_images?.[0];
  const imageSrc = imageSources[imageIndex] ?? imageSources[0];
  const href = record.samples.length ? `/katalog/${record.id}` : entry ? regionExploreHrefForEntry(entry) : `/katalog/${record.id}`;
  const setSaved = () => {
    const next = !favorite;
    const stored = savedCatalogIds();
    const updated = next ? [...new Set([...stored, record.id])] : stored.filter((id) => id !== record.id);
    try { window.localStorage.setItem(favoriteKey, JSON.stringify(updated)); } catch { /* Favorites are available for the current page session. */ }
    favoriteSubscribers.forEach((subscriber) => subscriber());
  };

  return (
    <article className="catalog-card rise" data-catalog-id={record.id} style={{ "--d": `${Math.min(index, 4) * 45}ms` } as CSSProperties}>
      <div className="catalog-card-media">
      <Link className="catalog-card-photo" href={href} aria-label={`Lihat kain ${record.name} dan motifnya`}>
        {imageSrc ? (
          <CatalogImage
            src={imageSrc}
            alt={sample ? `Ilustrasi katalog ${record.name} · ${sample.label}` : image?.caption ?? `Referensi visual ${record.name}`}
            priority={index < 3}
          />
        ) : <span className="catalog-card-photo-empty">Visual kain belum tersedia</span>}
      </Link>
      <button type="button" className={`catalog-card-favorite${favorite ? " is-favorite" : ""}`} aria-label={favorite ? `Hapus ${record.name} dari kain tersimpan` : `Simpan ${record.name}`} aria-pressed={favorite} onClick={setSaved}><Heart size={20} strokeWidth={1.8} fill={favorite ? "currentColor" : "none"} /></button>
      {imageSources.length > 1 && <div className="catalog-card-thumbnails" aria-label={`Foto ${record.name}`}>{imageSources.map((source, viewIndex) => <button type="button" key={`${source}-${viewIndex}`} aria-label={`Lihat foto ${viewIndex + 1} ${record.name}`} aria-pressed={imageIndex === viewIndex} onClick={() => setImageIndex(viewIndex)}><img src={source} alt="" loading="lazy" /></button>)}</div>}
      </div>
      <div className="catalog-card-information">
        <div className="catalog-card-title-row"><h2><Link href={href}>{record.name}</Link></h2><span className="catalog-card-price">{availability.listing_count > 0 && availability.min_price_idr != null ? `Mulai dari ${idr(availability.min_price_idr)}` : "—"}</span></div>
        <p className="catalog-card-meta">{record.region}{record.technique ? ` · ${record.technique}` : ""}</p>
        <div className="catalog-card-details-row"><span>{availability.listing_count > 0 ? `${availability.listing_count} penawaran` : "Belum ada penawaran"}</span></div>
      </div>
    </article>
  );
}

function FilterSection({ title, children, defaultOpen = false }: { title: string; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <div className={`catalog-accordion${open ? " is-open" : ""}`}>
      <button type="button" className="catalog-accordion-trigger" id={`${id}-trigger`} aria-expanded={open} aria-controls={`${id}-content`} onClick={() => setOpen((value) => !value)}>
        {title}<ChevronRight size={14} aria-hidden="true" />
      </button>
      <div className="catalog-accordion-collapse" id={`${id}-content`} role="region" aria-labelledby={`${id}-trigger`} inert={!open}>
        <div className="catalog-accordion-inner"><div className="catalog-accordion-options">{children}</div></div>
      </div>
    </div>
  );
}

export function CatalogBrowser({ records, initialQuery = "", initialRegion = "" }: { records: CatalogRecord[]; initialQuery?: string; initialRegion?: string }) {
  const id = useId();
  const [query, setQuery] = useState(initialQuery);
  const [region, setRegion] = useState<string[]>([]);
  const [exploreRegion, setExploreRegion] = useState(findExploreRegion(initialRegion));
  const [technique, setTechnique] = useState<string[]>([]);
  const [inStock, setInStock] = useState(false);
  const [sort, setSort] = useState("curated");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const compactFilters = useSyncExternalStore(subscribeCompactFilters, () => window.matchMedia(compactFiltersQuery).matches, () => false);
  const grid = useRef<HTMLDivElement>(null);
  const positions = useRef<{ width: number; cards: Map<string, { left: number; top: number; visible: boolean }> }>({ width: 0, cards: new Map() });
  const regions = [...new Set(records.map(({ region }) => region).filter(Boolean))].sort((a, b) => a.localeCompare(b, "id"));
  const techniques = [...new Set(records.map(({ technique }) => technique).filter((value): value is string => Boolean(value)))].sort((a, b) => a.localeCompare(b, "id"));
  const words = normalize(query).split(/\s+/).filter(Boolean);
  const results = records
    .filter((record) => {
      const searchable = normalize([
        record.name,
        record.region,
        record.technique,
        record.summary,
        ...record.aliases,
        record.entry?.name,
        record.entry?.kind,
        record.entry?.textile_type,
        record.entry?.technique,
        record.entry?.region,
        record.entry?.community,
        record.entry?.summary,
        ...(record.entry?.aliases ?? []),
        ...record.samples.flatMap((sample) => [sample.code, sample.origin, sample.motif]),
      ].filter(Boolean).join(" "));
      return words.every((word) => searchable.includes(word)) &&
        (!exploreRegion || record.regionId === exploreRegion.id) &&
        (!region.length || region.includes(record.region)) &&
        (!technique.length || (record.technique !== null && technique.includes(record.technique))) &&
        (!inStock || record.availability.listing_count > 0);
    })
    .sort((a, b) => {
      if (sort === "az") return a.name.localeCompare(b.name, "id");
      if (sort === "price") {
        const priceA = a.availability.min_price_idr;
        const priceB = b.availability.min_price_idr;
        if (priceA == null) return priceB == null ? 0 : 1;
        if (priceB == null) return -1;
        return priceA - priceB;
      }
      return records.indexOf(a) - records.indexOf(b);
    });
  const resultsKey = results.map((record) => record.id).join("|");
  useLayoutEffect(() => {
    const element = grid.current;
    if (!element) { positions.current = { width: 0, cards: new Map() }; return; }
    const next: typeof positions.current = { width: element.clientWidth, cards: new Map() };
    const animations: Animation[] = [];
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    for (const card of Array.from(element.children) as HTMLElement[]) {
      const id = card.dataset.catalogId!;
      const current = { left: card.offsetLeft, top: card.offsetTop, visible: card.classList.contains("in") };
      const previous = positions.current.cards.get(id);
      next.cards.set(id, current);
      if (!reduced.matches && next.width === positions.current.width && previous && current.visible) {
        const x = previous.left - current.left;
        const y = previous.top - current.top;
        if (x || y) animations.push(card.animate([{ transform: `translate(${x}px, ${y}px)` }, { transform: "translate(0, 0)" }], { duration: 550, easing: "cubic-bezier(.22, 1, .36, 1)" }));
      }
    }
    positions.current = next;
    const cancel = () => animations.forEach((animation) => animation.cancel());
    reduced.addEventListener("change", cancel);
    return () => { cancel(); reduced.removeEventListener("change", cancel); };
  }, [resultsKey]);
  const activeFilters = region.length + technique.length + Number(inStock) + Number(!!exploreRegion);
  const toggle = (value: string, selected: string[], setSelected: (values: string[]) => void) =>
    setSelected(selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value]);
  const reset = () => {
    setQuery("");
    setRegion([]);
    setExploreRegion(undefined);
    setTechnique([]);
    setInStock(false);
    setSort("curated");
  };

  return (
    <div className="catalog-browser">
      <div className="catalog-mobile-filter-bar">
        <button type="button" aria-expanded={filtersOpen} aria-controls={`${id}-filters`} onClick={() => setFiltersOpen((open) => !open)}>
          <SlidersHorizontal size={17} aria-hidden="true" />
          Filter{activeFilters > 0 ? ` (${activeFilters})` : ""}
          <ChevronDown size={16} aria-hidden="true" />
        </button>
        <span>{results.length} kain</span>
      </div>

      <aside className={`catalog-filters${filtersOpen ? " catalog-filters-open" : ""}`} id={`${id}-filters`} aria-label="Filter katalog kain" aria-hidden={compactFilters && !filtersOpen ? true : undefined} inert={compactFilters && !filtersOpen}>
        <div className="catalog-filter-content"><div className="catalog-filter-inner">
        <div className="catalog-filters-title">
          <span>Filter Katalog</span>
          <button type="button" onClick={() => setFiltersOpen(false)} aria-label="Tutup filter"><X size={18} /></button>
        </div>
        <label className="catalog-sort" htmlFor={`${id}-sort`}>
          <span>Urutkan</span>
          <select id={`${id}-sort`} value={sort} onChange={(event) => setSort(event.target.value)}>
            <option value="curated">Pilihan Tenara</option>
            <option value="az">Nama A–Z</option>
            <option value="price">Harga terendah</option>
          </select>
        </label>
        <FilterSection title="Daerah asal" defaultOpen>
          {regions.map((value) => (
            <label className="catalog-filter-option" key={value}>
              <input type="checkbox" checked={region.includes(value)} onChange={() => toggle(value, region, setRegion)} />
              <span>{value}</span>
            </label>
          ))}
        </FilterSection>
        <FilterSection title="Teknik">
          {techniques.map((value) => (
            <label className="catalog-filter-option" key={value}>
              <input type="checkbox" checked={technique.includes(value)} onChange={() => toggle(value, technique, setTechnique)} />
              <span>{value}</span>
            </label>
          ))}
        </FilterSection>
        <FilterSection title="Cari tenun" defaultOpen={Boolean(initialQuery)}>
          <label className="catalog-search" htmlFor={`${id}-search-sidebar`}>
            <Search size={16} aria-hidden="true" />
            <span className="catalog-sr-only">Cari nama kain, daerah, atau teknik</span>
            <input id={`${id}-search-sidebar`} type="search" placeholder="Nama atau daerah…" value={query} onChange={(event) => setQuery(event.target.value)} />
            {query && <button type="button" aria-label="Hapus pencarian" onClick={() => setQuery("")}><X size={16} aria-hidden="true" /></button>}
          </label>
        </FilterSection>
        <FilterSection title="Ketersediaan">
          <label className="catalog-filter-option">
            <input type="checkbox" checked={inStock} onChange={(event) => setInStock(event.target.checked)} />
            <span>Dengan penawaran aktif</span>
          </label>
        </FilterSection>
        <button type="button" className="catalog-reset" onClick={reset}>Reset filter</button>
        </div></div>
      </aside>

      <section className="catalog-results" aria-label="Koleksi kain Nusantara">
        <div className="catalog-result-meta">
          <p role="status" aria-live="polite">{results.length} kain ditemukan</p>
        </div>
        {(query.trim() || activeFilters > 0) && (
          <div className="catalog-active-filters" aria-label="Filter aktif">
            {query.trim() && <button type="button" onClick={() => setQuery("")}><span>“{query.trim()}”</span><X size={14} aria-hidden="true" /></button>}
            {region.map((value) => <button key={value} type="button" onClick={() => toggle(value, region, setRegion)}><span>{value}</span><X size={14} aria-hidden="true" /></button>)}
            {exploreRegion && <button type="button" onClick={() => setExploreRegion(undefined)}><span>{exploreRegion.name}</span><X size={14} aria-hidden="true" /></button>}
            {technique.map((value) => <button key={value} type="button" onClick={() => toggle(value, technique, setTechnique)}><span>{value}</span><X size={14} aria-hidden="true" /></button>)}
            {inStock && <button type="button" onClick={() => setInStock(false)}><span>Penawaran aktif</span><X size={14} aria-hidden="true" /></button>}
          </div>
        )}
        {results.length > 0 ? (
          <div className="catalog-card-grid" ref={grid}>
            {results.map((record) => <CatalogCard key={record.id} record={record} index={records.indexOf(record)} />)}
          </div>
        ) : (
          <div className="catalog-empty">
            <Search size={32} strokeWidth={1.3} aria-hidden="true" />
            <p className="catalog-kicker">Masih banyak untuk dijelajahi</p>
            <h2>Belum menemukan kain yang sesuai.</h2>
            <p>Coba nama kain atau daerah lain, atau reset filter untuk melihat seluruh koleksi.</p>
            <button type="button" className="catalog-button" onClick={reset}>Lihat semua kain <ArrowRight size={17} aria-hidden="true" /></button>
          </div>
        )}
      </section>
    </div>
  );
}
