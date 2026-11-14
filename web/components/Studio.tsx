"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { ArrowLeft, ArrowUpRight, Check, Layers2, LoaderCircle, Ruler, Scissors, Shirt, Sparkles, Users } from "lucide-react";
import type { Listing } from "./ListingCard";
import { fileUrl, idr } from "@/lib/api";
import "./studio.css";

export const STUDIO_STEPS = [
  { title: "Pilih model", description: "Bentuk pakaian", icon: Shirt },
  { title: "Desain", description: "Detail & motif", icon: Scissors },
  { title: "Ukuran & Fit On", description: "Pas di badanmu", icon: Ruler },
  { title: "Kebutuhan kain", description: "Hitung bahan", icon: Layers2 },
  { title: "Pilih penjahit", description: "Wujudkan desain", icon: Users },
];

export function StudioLoading() {
  return (
    <section className="studio-loading" role="status" aria-live="polite">
      <div className="studio-loading-heading">
        <span className="studio-loading-eyebrow"><Scissors size={15} /> Studio Tenara</span>
        <h1>Menyiapkan studio</h1>
        <p>Memuat kain dan pilihan model untuk mulai merancang.</p>
      </div>

      <div className="studio-loading-steps" aria-hidden="true">
        {STUDIO_STEPS.map(({ title }, index) => (
          <div className="studio-loading-step" key={title}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <i />
            <small>{title}</small>
          </div>
        ))}
      </div>

      <div className="studio-loading-workbench" aria-hidden="true">
        <div className="studio-loading-canvas">
          <div className="studio-loading-toolbar"><i /><i /></div>
          <div className="studio-loading-fabric" />
          <div className="studio-loading-caption"><i /><i /></div>
        </div>
        <div className="studio-loading-panel">
          <i className="studio-loading-line studio-loading-line-title" />
          <i className="studio-loading-line studio-loading-line-copy" />
          <div className="studio-loading-options"><i /><i /><i /></div>
          <i className="studio-loading-line studio-loading-line-copy" />
        </div>
      </div>

      <p className="studio-loading-status"><LoaderCircle size={16} /> Kain pilihanmu sedang dimuat…</p>
    </section>
  );
}

export function StudioShell({ listingId, step = 0, onStep, canvas, children, footer }: {
  listingId?: string; step?: number; onStep?: (step: number) => void;
  canvas: ReactNode; children: ReactNode; footer: ReactNode;
}) {
  return <div className="design-studio">
    <header className="studio-heading">
      <div><Link href={listingId ? `/listings/${listingId}` : "/galeri"} className="studio-back"><ArrowLeft size={15} /> Kembali ke kain</Link>
        <div className="studio-title"><h1>Rancang bajumu</h1><span>STUDIO TENARA</span></div>
        <p>Dari kain pilihan, menjadi karya yang personal.</p>
      </div>
      <span className="studio-heading-note"><Scissors size={17} /> Dibuat untukmu, dengan ceritamu.</span>
    </header>
    <nav className="studio-steps" aria-label="Tahapan studio">
      {STUDIO_STEPS.map(({ title, description, icon: Icon }, index) => <button key={title} type="button" aria-current={step === index ? "step" : undefined} disabled={!onStep && index !== step} onClick={() => onStep?.(index)}>
        <span className="studio-step-number">{index + 1}</span><Icon size={18} className="studio-step-icon" /><span><strong>{title}</strong><small>{description}</small></span>
      </button>)}
    </nav>
    <div className="studio-workbench"><aside className="studio-canvas-column">{canvas}</aside><div className="studio-controls">{children}</div></div>
    <footer className="studio-bottom-bar">{footer}</footer>
  </div>;
}

const GARMENTS: Record<string, string> = {
  T01: "M42 27 62 19Q80 36 98 19L118 27 141 54 121 71 109 58 112 131 48 131 51 58 39 71 19 54Z",
  T02: "M44 27 63 20Q80 43 97 20L116 27 135 66 117 78 106 55 106 93 117 131 43 131 54 93 54 55 43 78 25 66Z",
  T03: "M51 27 66 20 80 48 94 20 109 27Q103 52 115 62L112 123 92 135 80 128 68 135 48 123 45 62Q57 52 51 27Z",
  T04: "M45 26 64 19 80 31 96 19 115 26 143 99 123 107 107 62 114 135 46 135 53 62 37 107 17 99Z",
  T05: "M45 24 64 18Q80 38 96 18L115 24 137 89 118 98 106 59 118 143 42 143 54 59 42 98 23 89Z",
};

export function GarmentDrawing({ code, large = false }: { code: string; large?: boolean }) {
  return <svg viewBox="0 0 160 160" fill="none" aria-hidden="true" className={large ? "studio-garment studio-garment-large" : "studio-garment"}>
    <path d={GARMENTS[code] ?? GARMENTS.T01} fill="currentColor" fillOpacity=".055" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    {code === "T01" && <><path d="m62 19 5 24 13-11 13 11 5-24M80 33v96M93 60h13v15H93z" stroke="currentColor" strokeWidth="1.3" /><path d="M80 54h.1M80 72h.1M80 90h.1M80 108h.1" stroke="currentColor" strokeWidth="3" strokeLinecap="round" /></>}
    {code === "T02" && <path d="M57 92q23 9 46 0M80 40v26m-4-5 4 5 4-5" stroke="currentColor" strokeWidth="1.3" />}
    {code === "T03" && <><path d="M80 48v80m-26-32h16m20 0h16" stroke="currentColor" strokeWidth="1.3" /><path d="M85 68h.1M85 85h.1M85 102h.1" stroke="currentColor" strokeWidth="3" strokeLinecap="round" /></>}
    {code === "T04" && <path d="m64 19 6 31 10-19 10 19 6-31M70 50l4 85m16-85-4 85M53 96h14v17H53m40-17h14v17H93" stroke="currentColor" strokeWidth="1.3" />}
    {code === "T05" && <path d="M80 34v34m-4-5 4 5 4-5M46 130h68M43 140v-13m74 13v-13" stroke="currentColor" strokeWidth="1.3" />}
    {large && <path d="M21 150h118" stroke="currentColor" strokeOpacity=".18" />}
  </svg>;
}

export type StudioTemplate = { code: string; name: string; compatible: boolean; reasons: string[] };
export function ModelChoices({ templates, selected, disabled, onSelect }: {
  templates: StudioTemplate[]; selected: string; disabled?: boolean; onSelect: (code: string) => void;
}) {
  return <div className="studio-model-grid" role="group" aria-label="Model pakaian">
    {templates.map((template) => <button key={template.code} type="button" aria-pressed={selected === template.code} disabled={disabled || !template.compatible} onClick={() => onSelect(template.code)}>
      <span className="studio-model-art"><GarmentDrawing code={template.code} />{selected === template.code && <span className="studio-model-check"><Check size={12} /></span>}</span>
      <strong>{template.name}</strong>{!template.compatible && <small>{template.reasons.join(" · ")}</small>}
    </button>)}
  </div>;
}

export function StudioCanvas({ listing, model, illustration, toolbar, children, loading = false }: {
  listing: Listing | null; model?: { code: string; name: string };
  illustration?: { url: string; label: string } | null; toolbar?: ReactNode; children?: ReactNode; loading?: boolean;
}) {
  const [view, setView] = useState<"fabric" | "design">(model ? "design" : "fabric");
  const image = listing?.images[0];
  return <div className="studio-canvas">
    <div className="studio-canvas-top"><span><Shirt size={16} /> Meja rancangan</span><span className="studio-live-label">{loading ? "Memuat kain…" : "Ruang kreasimu"}</span></div>
    <div className="studio-view-switch" role="group" aria-label="Tampilan preview">
      <button type="button" aria-pressed={view === "fabric"} onClick={() => setView("fabric")}><Layers2 size={14} /> Kain pilihan</button>
      <button type="button" aria-pressed={view === "design"} onClick={() => setView("design")}><Shirt size={14} /> {illustration ? "Ilustrasi desain" : "Pola model"}</button>
    </div>
    <div className={`studio-stage studio-stage-${view}`}>
      <span className="studio-stage-corner studio-stage-corner-tl" /><span className="studio-stage-corner studio-stage-corner-br" />
      <div className="studio-stage-content" key={`${view}-${view === "design" ? illustration?.url ?? model?.code ?? "empty" : image?.url ?? "empty"}`}>
      {view === "fabric" ? image ? <img className="studio-fabric-photo" src={fileUrl(image.url)} alt={image.caption ?? listing!.title} /> : <div className="studio-stage-empty"><Layers2 size={36} /><p>{loading ? "Menyiapkan kain pilihanmu…" : "Foto kain belum tersedia"}</p></div>
        : illustration ? <figure className="studio-illustration"><img src={fileUrl(illustration.url)} alt="Ilustrasi konseptual rancangan pakaian" /><figcaption>{illustration.label}</figcaption></figure>
          : <div className="studio-pattern">{model ? <><GarmentDrawing code={model.code} large /><h3>{model.name}</h3><p>Pola dasar · detail akhir mengikuti desainmu</p></> : <><Shirt size={70} strokeWidth={1} /><h3>Awali dengan sebuah model</h3><p>Pilih bentuk pakaian untuk mulai merancang.</p></>}</div>}
      </div>
      <span className="studio-stage-label">{view === "fabric" ? "TEKSTUR & MOTIF ASLI" : illustration ? "ILUSTRASI KONSEPTUAL" : "POLA DASAR PAKAIAN"}</span>
    </div>
    {toolbar && <div className="studio-preview-tools">{toolbar}</div>}
    {children && <div className="studio-preview-messages">{children}</div>}
    <div className="studio-fabric-info">
      {image && <img src={fileUrl(image.url)} alt="" />}
      <div><span>KAIN PILIHANMU</span><h2>{listing?.title ?? (loading ? "Memuat kain…" : "Kain pilihan")}</h2><p>{[listing?.merchant?.shop_name, listing?.material].filter(Boolean).join(" · ")}</p></div>
      {listing && <Link href={`/listings/${listing.id}`} aria-label="Lihat detail kain"><ArrowUpRight size={19} /></Link>}
    </div>
    {listing && <div className="studio-fabric-meta"><span>{listing.selling_unit === "meter" ? `Lebar ${listing.usable_width_cm ?? "—"} cm` : `${listing.piece_length_cm ?? "—"} × ${listing.piece_width_cm ?? "—"} cm`}</span><span>{idr(listing.price_idr)} / {listing.selling_unit === "meter" ? "meter" : "potong"}</span></div>}
    <p className="studio-canvas-caption"><Sparkles size={13} /> Setiap motif punya cerita. Kini, tambahkan ceritamu.</p>
  </div>;
}
