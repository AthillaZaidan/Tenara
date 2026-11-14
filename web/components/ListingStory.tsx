"use client";

import { useEffect } from "react";
import { api } from "@/lib/api";
import { Notice, useAction, useLoad } from "@/components/ui";
import { BookOpen } from "lucide-react";
import { WorkspacePanel } from "@/components/PartnerWorkspace";

type Story = { id: string; body: string; notes: string[]; citations: { chunk_id: string; source: string; license: string | null; urls: string[] }[] };
type Stories = { draft: Story | null; published: Story | null; job: { id: string; status: string; error: string | null } | null };

export function ListingStory({ listingId, hasScan }: { listingId: string; hasScan: boolean }) {
  const stories = useLoad(() => api<Stories>(`/listings/${listingId}/story`), listingId);
  const act = useAction();
  const running = stories.data?.job && ["queued", "processing"].includes(stories.data.job.status);
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(stories.reload, 3000);
    return () => clearInterval(timer);
  }, [running, stories.reload]);
  const draft = stories.data?.draft;
  return <WorkspacePanel title="Cerita di balik kain" description="Bawa pembeli lebih dekat dengan kisah karya Anda." icon={BookOpen}>
    <p>Cerita disusun dari hasil scan dan sumber yang disetujui. Tinjau draf sebelum menerbitkannya.</p>
    {!hasScan && <p className="text-base text-muted">Scan foto kain terlebih dahulu.</p>}
    {stories.loading && <p role="status">Memuat cerita kain…</p>}
    {stories.error && <Notice tone="error">{stories.error}</Notice>}{act.error && <Notice tone="error">{act.error}</Notice>}
    {running && <Notice>Cerita sedang dibuat. Proses dapat memerlukan waktu beberapa saat.</Notice>}
    {stories.data?.job?.status === "failed" && <Notice tone="error">{stories.data.job.error ?? "Cerita belum berhasil dibuat."}</Notice>}
    <button className="btn btn-quiet w-fit" disabled={act.busy || stories.loading || !!running || !hasScan} onClick={async () => {
      const result = await act.run(() => api(`/listings/${listingId}/story`, { method: "POST" }));
      if (result) stories.reload();
    }}>{draft ? "Buat draf baru" : "Buat draf cerita"}</button>
    {draft && <div className="grid gap-3 bg-surface p-5"><h4 className="text-lg font-medium">Draf untuk ditinjau</h4>
      {draft.body.split("\n").filter(Boolean).map((paragraph, i) => <p key={i}>{paragraph}</p>)}
      {draft.notes.length > 0 && <div><p>Catatan:</p><ul className="list-disc pl-5">{draft.notes.map((note) => <li key={note}>{note}</li>)}</ul></div>}
      {draft.citations.length > 0 && <div><p>Sumber:</p><ul className="list-disc pl-5">{draft.citations.map((c) => <li key={c.chunk_id}>{c.urls[0] ? <a className="link" href={c.urls[0]} target="_blank" rel="noreferrer">{c.source}</a> : c.source}{c.license && ` · ${c.license}`}</li>)}</ul></div>}
      <button className="btn w-fit" disabled={act.busy} onClick={async () => {
        const result = await act.run(() => api(`/listings/${listingId}/story/${draft.id}/publish`, { method: "POST" }));
        if (result) stories.reload();
      }}>Terbitkan cerita</button>
    </div>}
    {stories.data?.published && <div className="grid gap-2"><h4 className="text-lg font-medium">Cerita terbit</h4><p className="whitespace-pre-line">{stories.data.published.body}</p></div>}
  </WorkspacePanel>;
}
