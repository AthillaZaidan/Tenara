"use client";

import { Component, useCallback, useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import { fileUrl } from "@/lib/api";
import type { Entry } from "@/lib/types";
import type { GalleryVariant } from "@/lib/variants";
import { regionExploreHrefForEntry } from "@/lib/regions";

type Reference = { url: string; caption: string | null; credit: string | null; license: string | null };
const TextileStudyScene = dynamic(() => import("@/components/TextileStudyScene"), { ssr: false });

class SceneBoundary extends Component<{ children: ReactNode; onFailure: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { this.props.onFailure(); }
  render() { return this.state.failed ? null : this.props.children; }
}

export function TextileStudy({ entry, references, variants, initialVariant, story, notice }: {
  entry: Entry; references: Reference[]; variants: GalleryVariant[]; initialVariant: string;
  story: { body: string; unresolved: string[] } | null; notice: string;
}) {
  const [variantId, setVariantId] = useState(variants.some((v) => v.id === initialVariant) ? initialVariant : "");
  const [index, setIndex] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [failed, setFailed] = useState(false);
  const [mode, setMode] = useState<"photo" | "3d">("photo");
  const [sceneReady, setSceneReady] = useState(false);
  const [sceneFailed, setSceneFailed] = useState(false);
  const [rotation, setRotation] = useState(0);
  const [reset, setReset] = useState(0);
  const onSceneReady = useCallback(() => setSceneReady(true), []);
  const onSceneFailure = useCallback(() => { setSceneFailed(true); setMode("photo"); }, []);
  useEffect(() => {
    if (mode !== "3d" || sceneReady) return;
    const timeout = window.setTimeout(onSceneFailure, 15000);
    return () => window.clearTimeout(timeout);
  }, [mode, sceneReady, onSceneFailure]);
  const variant = variants.find((v) => v.id === variantId);
  const images = variant ? variant.images : references;
  const image = images[index];
  const selectVariant = (id: string) => { setVariantId(id); setIndex(0); setZoom(1); setFailed(false); setSceneReady(false); };
  return <div className="grid gap-8">
    <div className="grid gap-3"><p className="text-sm uppercase tracking-[.18em]">Ruang studi kain</p><h1 className="t-head">{entry.name}</h1><p>{[entry.region, entry.community, entry.technique].filter(Boolean).join(" · ")}</p></div>
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.8fr)]">
      <section className="grid content-start gap-4" aria-label="Gambar referensi kain">
        <div className="flex flex-wrap gap-2" aria-label="Mode tampilan"><button className={`rounded-full px-4 py-2 ${mode === "photo" ? "bg-field text-field-ink" : "bg-surface"}`} aria-pressed={mode === "photo"} onClick={() => setMode("photo")}>Foto</button><button className={`rounded-full px-4 py-2 ${mode === "3d" ? "bg-field text-field-ink" : "bg-surface"}`} aria-pressed={mode === "3d"} disabled={!image || sceneFailed} onClick={() => { setSceneReady(false); setMode("3d"); }}>Ruang 3D</button></div>
        <div className="relative flex min-h-80 items-center justify-center overflow-hidden rounded-2xl bg-surface sm:min-h-[32rem]">
          {mode === "3d" && image ? <><SceneBoundary key={image.url} onFailure={onSceneFailure}><div className="absolute inset-0" role="img" aria-label={`Presentasi 3D gambar referensi ${variant?.name ?? entry.name}`}><TextileStudyScene imageUrl={fileUrl(image.url)} zoom={(zoom - 1) * 2} rotation={rotation} reset={reset} onReady={onSceneReady} onFailure={onSceneFailure} /></div></SceneBoundary>{!sceneReady && <p className="z-10 p-6">Menyiapkan ruang 3D…</p>}</> : image && !failed ? <img key={image.url} src={fileUrl(image.url)} alt={image.caption ?? `Referensi ${variant?.name ?? entry.name}`} onError={() => setFailed(true)} style={{ transform: `scale(${zoom})` }} className="max-h-[65vh] w-full object-contain transition-transform duration-200" /> : <p className="p-6 text-center">{failed ? "Gambar referensi belum dapat dimuat." : "Belum ada gambar referensi untuk pilihan ini."}</p>}
        </div>
        {sceneFailed && <p role="status" className="text-base">Ruang 3D tidak tersedia; tampilan foto tetap dapat digunakan.</p>}
        {mode === "3d" && <div className="flex flex-wrap gap-2"><button className="btn btn-quiet" onClick={() => setRotation(Math.max(-0.45, rotation - 0.15))}>Putar kiri</button><button className="btn btn-quiet" onClick={() => setRotation(Math.min(0.45, rotation + 0.15))}>Putar kanan</button><button className="btn btn-quiet" onClick={() => { setRotation(0); setZoom(1); setReset((value) => value + 1); }}>Atur posisi awal</button><p className="w-full text-sm text-muted">Presentasi visual dari foto referensi, bukan simulasi sifat kain.</p></div>}
        <div className="flex flex-wrap items-center gap-3"><button className="btn btn-quiet" disabled={!image || zoom <= 1} onClick={() => setZoom(Math.max(1, zoom - 0.25))} aria-label="Perkecil gambar">−</button><span aria-live="polite">{Math.round(zoom * 100)}%</span><button className="btn btn-quiet" disabled={!image || zoom >= 3} onClick={() => setZoom(Math.min(3, zoom + 0.25))} aria-label="Perbesar gambar">+</button><button className="link" disabled={!image || zoom === 1} onClick={() => setZoom(1)}>Atur ulang</button></div>
        {image && <p className="text-sm text-muted">{[image.caption, image.credit, image.license].filter(Boolean).join(" · ") || "Gambar referensi"}</p>}
        {images.length > 1 && <div className="flex flex-wrap gap-3" aria-label="Pilih gambar referensi">{images.map((item, i) => <button key={item.url} aria-label={`Gambar referensi ${i + 1}`} aria-pressed={i === index} onClick={() => { setIndex(i); setZoom(1); setFailed(false); setSceneReady(false); }} className={`h-20 w-20 overflow-hidden rounded-md border-2 ${i === index ? "border-current" : "border-transparent"}`}><img src={fileUrl(item.url)} alt="" className="h-full w-full object-cover" /></button>)}</div>}
      </section>
      <aside className="grid content-start gap-6 rounded-2xl bg-white/60 p-6 sm:p-8">
        {variants.length > 0 && <label className="grid gap-2 text-base">Pilihan motif<select className="field" value={variantId} onChange={(event) => selectVariant(event.target.value)}><option value="">Referensi kain umum</option>{variants.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
        {variant ? <><h2 className="text-xl font-semibold">{variant.name}</h2>{variant.description && <p>{variant.description}</p>}</> : <><h2 className="text-xl font-semibold">Tentang kain ini</h2>{entry.summary && <p>{entry.summary}</p>}</>}
        {story && <div className="grid gap-3 border-t border-current/15 pt-5"><h3 className="text-lg font-semibold">Cerita budaya</h3>{story.body.split("\n").filter(Boolean).map((paragraph, i) => <p key={i} className="text-base">{paragraph}</p>)}{story.unresolved.length > 0 && <p className="text-base text-muted">Belum terverifikasi: {story.unresolved.join("; ")}</p>}</div>}
        <p className="text-sm text-muted">{notice}</p>
        <Link href={`/gallery/${entry.slug}${variantId ? `?variant=${encodeURIComponent(variantId)}#listings` : "#listings"}`} className="btn w-fit">Lihat penawaran kain</Link>
        <Link href={regionExploreHrefForEntry(entry)} className="link w-fit text-base">Jelajahi daerah asal</Link>
      </aside>
    </div>
  </div>;
}
