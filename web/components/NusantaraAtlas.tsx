"use client";

import { Component, useCallback, useEffect, useState, type ReactNode } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import type { Entry } from "@/lib/types";
import type { RegionId } from "@/lib/exploration";
import { entriesForRegion, regionExploreHrefForEntry, regions } from "@/lib/regions";
import { RegionalStories } from "@/components/RegionalStories";
import { AtlasMap } from "@/components/atlas/AtlasMap";

const RegionalDiorama = dynamic(() => import("@/components/diorama/RegionalDiorama"), { ssr: false });

class DioramaBoundary extends Component<{ children: ReactNode; onFailure: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { this.props.onFailure(); }
  render() { return this.state.failed ? null : this.props.children; }
}

function regionId(value: string | null): RegionId | "" {
  return regions.find((item) => item.id === value)?.id ?? "";
}

export function NusantaraAtlas({ entries, initialRegion = "" }: { entries: Entry[]; initialRegion?: string }) {
  const [selected, setSelected] = useState<RegionId | "">(() => regionId(initialRegion));
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [show3d, setShow3d] = useState(true);
  const [rotation, setRotation] = useState(0);
  const [atlasFailed, setAtlasFailed] = useState(false);
  const onReady = useCallback(() => setReady(true), []);
  const onFailure = useCallback(() => setFailed(true), []);
  useEffect(() => {
    const update = () => { setSelected(regionId(new URLSearchParams(window.location.search).get("daerah"))); setReady(false); setFailed(false); };
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);
  useEffect(() => {
    if (!selected || !show3d || ready || failed) return;
    const timeout = window.setTimeout(onFailure, 15000);
    return () => window.clearTimeout(timeout);
  }, [selected, show3d, ready, failed, onFailure]);
  const select = (id: RegionId | "") => {
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("daerah", id); else url.searchParams.delete("daerah");
    window.history.pushState(null, "", `${url.pathname}${url.search}${url.hash}`);
    setSelected(id); setReady(false); setFailed(false); setRotation(0);
  };
  const region = regions.find((item) => item.id === selected);
  const visible = region ? entriesForRegion(entries, region) : entries;

  return <div className="grid gap-8">
    <div className="overflow-hidden rounded-3xl bg-[#d9eeeb] p-5 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm font-semibold uppercase tracking-[.18em]">Jelajahi Nusantara</p>{region && <button className="btn btn-quiet" onClick={() => select("")}>← Kembali ke peta</button>}</div>
      {region ? <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(240px,.7fr)]">
        <div className="relative h-[340px] overflow-hidden rounded-2xl bg-[#b5e2df] sm:h-[470px]">
          {show3d && !failed ? <DioramaBoundary key={region.id} onFailure={onFailure}><div role="img" aria-label={`Diorama ilustratif ${region.name}. Gunakan mouse, sentuhan, atau tombol untuk memutar.`} className="absolute inset-0"><RegionalDiorama region={region.id} rotation={rotation} onReady={onReady} onFailure={onFailure} /></div></DioramaBoundary> : <img src="/img/atlas-nusantara.webp" alt="Ilustrasi kepulauan Nusantara" className="h-full w-full object-contain p-6" />}
          {show3d && !ready && !failed && <p role="status" className="absolute left-4 top-4 rounded-lg bg-bg p-3 text-sm">Menyiapkan diorama…</p>}
        </div>
        <div className="grid content-center gap-4"><p className="text-sm uppercase tracking-wider">Pintu menuju daerah</p><h2 className="t-head">{region.name}</h2><p className="text-base">Diorama ini adalah ilustrasi lingkungan, bukan rekonstruksi suatu kampung tertentu.</p><p className="text-base">{visible.length ? `${visible.length} entri terbit terkait nama atau metadata daerah ini.` : "Belum ada entri terbit yang terhubung dengan daerah ini."}</p>{show3d && !failed && <div className="flex flex-wrap gap-2"><button className="btn btn-quiet" onClick={() => setRotation((value) => value - Math.PI / 8)}>Putar kiri</button><button className="btn btn-quiet" onClick={() => setRotation((value) => value + Math.PI / 8)}>Putar kanan</button><button className="btn btn-quiet" onClick={() => setRotation(0)}>Atur ulang</button></div>}<button className="link w-fit text-base" onClick={() => { setShow3d(!show3d); setReady(false); setFailed(false); }}>{show3d ? "Gunakan tampilan foto" : "Tampilkan diorama 3D"}</button>{failed && <p role="status" className="text-base">Diorama tidak tersedia; gunakan daftar kain di bawah.</p>}</div>
      </div> : <div className="mt-5">{!atlasFailed ? <AtlasMap selected={selected} onSelect={(id) => select(regionId(id))} onFailure={() => setAtlasFailed(true)} /> : <div className="overflow-x-auto"><div className="relative mx-auto min-w-[700px] max-w-6xl"><img src="/img/atlas-nusantara.webp" alt="Ilustrasi peta kepulauan Nusantara" className="w-full" />{regions.map((item) => <button key={item.id} type="button" onClick={() => select(item.id)} aria-label={`Jelajahi ${item.name}`} title={item.name} className="absolute -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-[#3d5a33] px-2 py-1 text-xs font-semibold text-white shadow-md hover:bg-[#5f4228]" style={{ left: `${item.position[0]}%`, top: `${item.position[1]}%` }}>{item.name}</button>)}</div></div>}</div>}
    </div>
    <section className="grid gap-5" aria-labelledby="regions-title"><div><h2 id="regions-title" className="t-head text-3xl">{region ? `Kain terkait ${region.name}` : "Pilih daerah"}</h2><p className="mt-3">{region ? "Jelajahi kain, cerita, dan sumber dari daerah ini." : "Pilih penanda pada peta atau nama daerah di bawah."}</p></div>
      {!region && <div className="flex flex-wrap gap-2">{regions.map((item) => <button key={item.id} className="rounded-full bg-surface px-5 py-3 text-base" onClick={() => select(item.id)}>{item.name}</button>)}</div>}
      {visible.length ? region ? <RegionalStories key={region.id} entries={visible} /> : <ul className="grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">{visible.map((entry) => <li key={entry.id}><Link href={regionExploreHrefForEntry(entry)} className="grid h-full content-start gap-3 rounded-xl bg-surface p-6 no-underline hover:underline"><span className="text-sm uppercase tracking-wider">{entry.region ?? "Nusantara"} · {entry.technique ?? "Tenun"}</span><h3 className="t-head text-3xl">{entry.name}</h3><p className="text-base">{entry.summary}</p><span className="mt-3 text-sm font-semibold">Jelajahi daerah →</span></Link></li>)}</ul> : <p>Belum ada entri terbit untuk daerah ini.</p>}
    </section>
  </div>;
}
