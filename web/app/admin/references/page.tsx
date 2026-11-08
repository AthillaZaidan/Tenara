"use client";

import Link from "next/link";
import { useState } from "react";
import { Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, fileUrl } from "@/lib/api";

type Ref = {
  id: string; tradition: string | null; style: "modern" | "archival"; source_label: string; source_url: string | null;
  credit: string | null; license: string | null; display_allowed: boolean; approval_status: string; url: string | null;
};
type Coverage = {
  min_refs: number; min_sources: number;
  items: { entry_id: string; tradition: string | null; modern_approved: number; modern_sources: number; archival_approved: number; pending: number; rejected: number; gives_verdict: boolean }[];
};

const STATUS: Record<string, string> = { pending: "Menunggu tinjauan", approved: "Disetujui", rejected: "Ditolak" };
const STYLE: Record<string, string> = { modern: "Modern (dipakai menilai)", archival: "Arsip (pembanding saja)" };

function CoverageTable({ data }: { data: Coverage }) {
  return (
    <div className="grid gap-3">
      <p className="max-w-[70ch] text-base">
        Sebuah tradisi baru bisa dinilai &ldquo;konsisten&rdquo; atau &ldquo;perlu dicek&rdquo; bila punya minimal {data.min_refs} foto modern yang disetujui dari {data.min_sources} sumber berbeda.
        Foto arsip museum hanya menjadi pembanding, karena foto kain lama tidak memprediksi foto kain baru dari penjual.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-left text-base">
          <thead className="text-muted"><tr><th className="py-2 pr-4 font-normal">Tradisi</th><th className="pr-4 font-normal">Modern (sumber)</th><th className="pr-4 font-normal">Arsip</th><th className="pr-4 font-normal">Menunggu</th><th className="font-normal">Bisa menilai</th></tr></thead>
          <tbody>
            {data.items.map((i) => (
              <tr key={i.entry_id} className="border-t border-[color:var(--surface)]">
                <td className="py-2 pr-4">{i.tradition}</td>
                <td className="pr-4">{i.modern_approved} ({i.modern_sources})</td>
                <td className="pr-4">{i.archival_approved}</td>
                <td className="pr-4">{i.pending}</td>
                <td>{i.gives_verdict ? "Ya" : "Belum"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Review() {
  const [status, setStatus] = useState("pending");
  const [style, setStyle] = useState("");
  const coverage = useLoad(() => api<Coverage>("/admin/reference-photos/coverage"), "coverage");
  const query = `/admin/reference-photos?limit=100&approval_status=${status}${style ? `&style=${style}` : ""}`;
  const list = useLoad(() => api<{ items: Ref[]; next_cursor: string | null }>(query), query);
  const act = useAction();
  const items = list.data?.items ?? [];
  const sources = [...new Set(items.map((r) => r.source_label))];
  const decide = async (body: Record<string, unknown>, confirmText?: string) => {
    if (confirmText && !window.confirm(confirmText)) return;
    const r = await act.run(() => api("/admin/reference-photos/decision", { body }));
    if (r) { list.reload(); coverage.reload(); }
  };
  return (
    <div className="grid gap-10">
      {coverage.data && <CoverageTable data={coverage.data} />}
      <div className="grid gap-5">
        <p className="flex flex-wrap gap-4 text-base">
          {Object.entries(STATUS).map(([k, v]) => <button key={k} onClick={() => setStatus(k)} className={k === status ? "link font-medium" : "cursor-pointer hover:underline underline-offset-4"}>{v}</button>)}
          <span className="text-muted">·</span>
          {[["", "Semua gaya"], ...Object.entries(STYLE)].map(([k, v]) => <button key={k || "all"} onClick={() => setStyle(k)} className={k === style ? "link font-medium" : "cursor-pointer hover:underline underline-offset-4"}>{v}</button>)}
        </p>
        {(list.error || act.error) && <Notice tone="error">{list.error || act.error}</Notice>}
        {status === "pending" && sources.length > 0 && (
          <div className="flex flex-wrap gap-3">
            {sources.map((s) => (
              <button key={s} className="btn btn-quiet" disabled={act.busy}
                onClick={() => decide({ decision: "approve", source_label: s }, `Setujui semua foto menunggu dari "${s}"? Pastikan labelnya sudah Anda periksa.`)}>
                Setujui semua dari {s}
              </button>
            ))}
          </div>
        )}
        {list.loading ? <p>Memuat…</p> : items.length === 0 ? <p>Tidak ada foto di status ini.</p> : (
          <ul className="grid list-none grid-cols-2 gap-4 p-0 sm:grid-cols-3 lg:grid-cols-4">
            {items.map((r) => (
              <li key={r.id} className="grid content-start gap-2 bg-surface p-3">
                {r.url ? <img src={fileUrl(r.url)} alt={`Foto referensi ${r.tradition ?? ""}`} className="aspect-square w-full object-cover" /> : <div className="aspect-square w-full" />}
                <span className="text-base font-medium">{r.tradition}</span>
                <span className="t-small text-muted">
                  {r.style === "modern" ? "Modern" : "Arsip"} · {r.source_url ? <a href={r.source_url} target="_blank" rel="noopener noreferrer" className="link">{r.source_label}</a> : r.source_label}
                  {r.license ? ` · ${r.license}` : " · lisensi belum jelas"}{r.display_allowed ? "" : " · tidak ditampilkan"}
                </span>
                {r.approval_status === "pending" && (
                  <span className="flex gap-2">
                    <button className="btn" disabled={act.busy} onClick={() => decide({ decision: "approve", ids: [r.id] })}>Setujui</button>
                    <button className="btn btn-quiet" disabled={act.busy} onClick={() => decide({ decision: "reject", ids: [r.id] })}>Tolak</button>
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
        {list.data?.next_cursor && <p className="t-small text-muted">Menampilkan 100 pertama; setujui atau tolak untuk melihat berikutnya.</p>}
      </div>
    </div>
  );
}

export default function AdminReferencesPage() {
  return (
    <Page>
      <p className="mb-2 mt-6 text-base"><Link href="/admin" className="link">← Admin</Link></p>
      <h1 className="t-head mb-4">Foto referensi</h1>
      <p className="mb-10 max-w-[70ch]">Foto berlabel tradisi untuk memeriksa klaim penjual lewat foto. Periksa labelnya: foto yang salah label membuat pemeriksaan menyesatkan. Hasil pemeriksaan hanya sinyal bantu; keputusan tetap di kurator.</p>
      <RequireAuth role="admin"><Review /></RequireAuth>
    </Page>
  );
}
