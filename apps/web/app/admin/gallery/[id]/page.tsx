"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api } from "@/lib/api";
import type { Entry } from "@/lib/types";

type Story = { id: string; revision: number; body: string; status: string; unresolved: string[]; review_note: string | null; citations: { source_id: string; chunk_id: string | null; locator: string | null }[] };
const STORY: Record<string, string> = { draft: "Draf", submitted: "Menunggu persetujuan", approved: "Disetujui", rejected: "Ditolak", superseded: "Digantikan" };

function Manage() {
  const { id } = useParams<{ id: string }>();
  const entry = useLoad(() => api<Entry>(`/admin/gallery/${id}`), id);
  const stories = useLoad(() => api<Story[]>(`/admin/gallery/${id}/stories`), id);
  const act = useAction();
  const [note, setNote] = useState("");
  const refresh = () => { entry.reload(); stories.reload(); };
  const go = async <T,>(fn: () => Promise<T>) => { const r = await act.run(fn); if (r !== undefined) refresh(); };
  if (entry.loading) return <p>Memuat…</p>;
  if (entry.error || !entry.data) return <Notice tone="error">{entry.error ?? "Entri tidak ditemukan."}</Notice>;
  const e = entry.data;
  return (
    <div className="grid max-w-3xl gap-10">
      <div>
        <p className="text-base text-muted">{e.status === "published" ? "Terbit" : e.status === "archived" ? "Diarsipkan" : "Draf"} · revisi {e.revision}</p>
        <h2 className="t-head" style={{ fontSize: "clamp(2rem, 1.3rem + 3.2vw, 3.5rem)" }}>{e.name}</h2>
        <p className="text-lg">{[e.technique, e.region, e.community].filter(Boolean).join(" · ")}</p>
      </div>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <div className="flex flex-wrap gap-3">
        <button className="btn" disabled={act.busy} onClick={() => go(() => api(`/admin/gallery/${id}/story/generate`, { method: "POST" }))}>Buat draf cerita dari sumber</button>
        {e.status !== "published" && <button className="btn btn-quiet" disabled={act.busy} onClick={() => go(() => api(`/admin/gallery/${id}/publish`, { method: "POST" }))}>Terbitkan entri</button>}
        {e.status !== "archived" && <button className="btn btn-quiet" disabled={act.busy} onClick={() => go(() => api(`/admin/gallery/${id}/archive`, { method: "POST" }))}>Arsipkan</button>}
        {e.status === "published" && <Link href={`/gallery/${e.slug}`} className="btn btn-quiet no-underline">Lihat halaman publik</Link>}
      </div>
      <p className="text-base text-muted">Penulis dan kritikus hanya memakai potongan dari sumber yang sudah disetujui, dan hasilnya selalu berupa draf yang harus Anda setujui. Tanpa sumber, sistem menolak menulis.</p>
      <h3 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Cerita</h3>
      <ul className="grid list-none gap-6 p-0">
        {stories.data?.map((s) => (
          <li key={s.id} className="grid gap-3 bg-surface p-5">
            <p className="text-base text-muted">Revisi {s.revision} · {STORY[s.status] ?? s.status} · {s.citations.length} kutipan</p>
            <div className="grid gap-2">{s.body.split("\n").map((p, i) => <p key={i}>{p}</p>)}</div>
            {s.unresolved.length > 0 && <ul className="list-disc pl-5 text-base">{s.unresolved.map((u) => <li key={u}>{u}</li>)}</ul>}
            {s.status === "draft" && <button className="btn w-fit" disabled={act.busy} onClick={() => go(() => api(`/admin/stories/${s.id}/submit`, { method: "POST" }))}>Ajukan untuk persetujuan</button>}
            {s.status === "submitted" && (
              <div className="grid gap-3">
                <Field label="Catatan keputusan"><input className="field" value={note} onChange={(ev) => setNote(ev.target.value)} /></Field>
                <div className="flex gap-3">
                  <button className="btn" disabled={act.busy} onClick={() => go(() => api(`/admin/stories/${s.id}/decision`, { body: { decision: "approve", reason: note || null } }))}>Setujui</button>
                  <button className="btn btn-quiet" disabled={act.busy || !note.trim()} onClick={() => go(() => api(`/admin/stories/${s.id}/decision`, { body: { decision: "reject", reason: note } }))}>Tolak</button>
                </div>
              </div>
            )}
            {s.review_note && <p className="text-base">Catatan: {s.review_note}</p>}
          </li>
        ))}
        {stories.data?.length === 0 && <li>Belum ada cerita.</li>}
      </ul>
    </div>
  );
}

export default function AdminEntryPage() {
  return (
    <Page>
      <p className="mb-2 mt-6 text-base"><Link href="/admin/gallery" className="link">← Kurasi Gallery</Link></p>
      <RequireAuth role="admin"><Manage /></RequireAuth>
    </Page>
  );
}
