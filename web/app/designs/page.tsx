"use client";

import Link from "next/link";
import { useState } from "react";
import { Bookmark, Layers, Sparkles } from "lucide-react";
import { api, when } from "@/lib/api";
import { Notice, RequireAuth, useAction, useLoad } from "@/components/ui";
import { CollectionEmptyState, CollectionLoading, PersonalCollection } from "@/components/PersonalCollection";

type Design = { id: string; listing_id: string; template: { name: string }; current_revision: number; created_at: string; ready_for_tailor_validation: boolean };
type DesignPage = { items: Design[]; next_cursor: string | null };

function SavedDesigns() {
  const first = useLoad(() => api<DesignPage>("/customizations?limit=20"), "designs");
  const act = useAction();
  const [additional, setAdditional] = useState<Design[]>([]);
  const [next, setNext] = useState<string | null | undefined>(undefined);
  const cursor = next === undefined ? first.data?.next_cursor : next;
  const items = [...(first.data?.items ?? []), ...additional];
  return <>
    <section className="personal-panel" aria-labelledby="saved-designs-heading">
      <div className="personal-panel-heading"><div className="personal-panel-title"><Bookmark size={17} strokeWidth={1.5} aria-hidden="true" /><h2 id="saved-designs-heading">Rancangan Anda</h2></div><span className="personal-count">{first.data ? `${items.length} desain` : "—"}</span></div>
      {first.error ? <div className="personal-feedback"><Notice tone="error">{first.error}</Notice><button className="btn btn-quiet" onClick={first.reload}>Coba lagi</button></div> : first.loading ? <CollectionLoading>Memuat desain…</CollectionLoading> : items.length === 0 ? <CollectionEmptyState kind="designs" title="Ide indah dimulai dari sehelai kain" description="Belum ada desain tersimpan. Temukan kain pilihan Anda, lalu rancang busana yang bercerita tentang Anda." href="/galeri" action="Temukan kain pilihan" /> :
        <ul className="personal-designs">{items.map((d) => <li key={d.id} className="personal-design-card"><Layers size={30} strokeWidth={1.2} aria-hidden="true" /><p className="personal-design-meta">{when(d.created_at)} · Revisi {d.current_revision}</p><h3>{d.template.name}</h3><p>{d.ready_for_tailor_validation ? "Siap diajukan ke penjahit" : "Lanjutkan rancangan Anda"}</p><div className="personal-design-actions"><Link className="btn" href={`/customize/${d.id}`}>Lanjutkan desain</Link><Link className="link" href={`/listings/${d.listing_id}`}>Lihat kain</Link></div></li>)}</ul>}
      {act.error && <div className="personal-feedback"><Notice tone="error">{act.error}</Notice></div>}
      {cursor && !first.error && <div className="personal-more"><button className="btn btn-quiet" disabled={act.busy} onClick={async () => {
      const result = await act.run(() => api<DesignPage>(`/customizations?limit=20&cursor=${encodeURIComponent(cursor)}`));
      if (result) { setAdditional((prev) => [...prev, ...result.items]); setNext(result.next_cursor); }
      }}>{act.busy ? "Memuat…" : "Muat lebih banyak"}</button></div>}
    </section>
    <p className="personal-note"><Sparkles size={13} aria-hidden="true" />Setiap rancangan menyimpan cerita. Lanjutkan kapan pun Anda siap.</p>
  </>;
}

export default function DesignsPage() {
  return <PersonalCollection title="Desain tersimpan" description="Simpan inspirasi, lanjutkan rancangan, dan wujudkan busana Anda."><RequireAuth loadingFallback={<CollectionLoading>Memuat desain…</CollectionLoading>}><SavedDesigns /></RequireAuth></PersonalCollection>;
}
