"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, fileUrl } from "@/lib/api";
import type { Entry } from "@/lib/types";
import { regionExploreHrefForEntry } from "@/lib/regions";
import { VariantManager } from "@/components/VariantManager";
import { Upload } from "@/components/Upload";

type Story = { id: string; revision: number; body: string; status: string; unresolved: string[]; review_note: string | null; citations: { source_id: string; chunk_id: string | null; locator: string | null }[] };
const STORY: Record<string, string> = { draft: "Draf", in_review: "Menunggu persetujuan", approved: "Disetujui", rejected: "Ditolak", superseded: "Digantikan" };

function EntryMetadataEditor({ entry, onSave }: { entry: Entry; onSave: (changes: Record<string, unknown>) => Promise<void> }) {
  const [draft, setDraft] = useState({ name: entry.name, kind: entry.kind, aliases: entry.aliases.join(", "), textile_type: entry.textile_type ?? "", technique: entry.technique ?? "", region: entry.region ?? "", community: entry.community ?? "", summary: entry.summary ?? "" });
  return <details className="rounded-xl bg-surface p-5"><summary className="cursor-pointer font-medium">Ubah metadata entri</summary><div className="mt-4 grid gap-4"><Field label="Nama"><input className="field" value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></Field><Field label="Jenis"><select className="field" value={draft.kind} onChange={(event) => setDraft({ ...draft, kind: event.target.value })}><option value="tradition">Tradisi</option><option value="textile">Tekstil</option><option value="motif">Motif</option></select></Field><Field label="Alias (pisahkan dengan koma)"><input className="field" value={draft.aliases} onChange={(event) => setDraft({ ...draft, aliases: event.target.value })} /></Field><div className="grid gap-4 sm:grid-cols-2">{([ ["textile_type", "Jenis kain"], ["technique", "Teknik"], ["region", "Daerah"], ["community", "Komunitas"] ] as const).map(([key, label]) => <Field key={key} label={label}><input className="field" value={draft[key]} onChange={(event) => setDraft({ ...draft, [key]: event.target.value })} /></Field>)}</div><Field label="Ringkasan"><textarea className="field" value={draft.summary} onChange={(event) => setDraft({ ...draft, summary: event.target.value })} /></Field><p className="text-sm">Pembaruan memakai revisi {entry.revision}; jika entri berubah di tab lain, muat ulang dahulu.</p><button className="btn w-fit" disabled={!draft.name.trim()} onClick={() => onSave({ expected_revision: entry.revision, ...draft, aliases: draft.aliases.split(",").map((alias) => alias.trim()).filter(Boolean), textile_type: draft.textile_type || null, technique: draft.technique || null, region: draft.region || null, community: draft.community || null })}>Simpan metadata</button></div></details>;
}

function Manage() {
  const { id } = useParams<{ id: string }>();
  const entry = useLoad(() => api<Entry>(`/admin/gallery/${id}`), id);
  const stories = useLoad(() => api<Story[]>(`/admin/gallery/${id}/stories`), id);
  const images = useLoad(() => api<{ id: string; url: string; caption: string | null; credit: string | null; license: string | null }[]>(`/admin/gallery/${id}/images`), id);
  const sources = useLoad(() => api<{ items: { id: string; title: string }[] }>("/admin/sources?approval_status=approved&limit=100"), id);
  const act = useAction();
  const [note, setNote] = useState("");
  const [caption, setCaption] = useState("");
  const [credit, setCredit] = useState("");
  const [license, setLicense] = useState("");
  const [storyBody, setStoryBody] = useState("");
  const [sourceIds, setSourceIds] = useState<string[]>([]);
  const refresh = () => { entry.reload(); stories.reload(); };
  const go = async <T,>(fn: () => Promise<T>) => { const r = await act.run(fn); if (r !== undefined) refresh(); };
  if (entry.loading) return <p>Memuat…</p>;
  if (entry.error || !entry.data) return <Notice tone="error">{entry.error ?? "Entri tidak ditemukan."}</Notice>;
  const e = entry.data;
  return (
    <div className="grid max-w-3xl gap-10">
      <div>
        <p className="text-base text-muted">{e.status === "published" ? "Terbit" : e.status === "archived" ? "Diarsipkan" : "Draf"} · revisi {e.revision}</p>
        <h1 className="t-head" style={{ fontSize: "clamp(2rem, 1.3rem + 3.2vw, 3.5rem)" }}>{e.name}</h1>
        <p className="text-lg">{[e.technique, e.region, e.community].filter(Boolean).join(" · ")}</p>
      </div>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <div className="flex flex-wrap gap-3">
        <button className="btn" disabled={act.busy} onClick={() => go(() => api(`/admin/gallery/${id}/story/generate`, { method: "POST" }))}>Buat draf cerita dari sumber</button>
        {e.status !== "published" && <button className="btn btn-quiet" disabled={act.busy} onClick={() => go(() => api(`/admin/gallery/${id}/publish`, { method: "POST" }))}>Terbitkan entri</button>}
        {e.status !== "archived" && <button className="btn btn-quiet" disabled={act.busy} onClick={() => go(() => api(`/admin/gallery/${id}/archive`, { method: "POST" }))}>Arsipkan</button>}
        {e.status === "published" && <Link href={regionExploreHrefForEntry(e)} className="btn btn-quiet no-underline">Lihat daerah di Galeri</Link>}
      </div>
      <EntryMetadataEditor key={`${e.id}-${e.revision}`} entry={e} onSave={async (changes) => { await go(() => api(`/admin/gallery/${id}`, { method: "PATCH", body: changes })); }} />
      <p className="text-base text-muted">Penulis dan kritikus hanya memakai potongan dari sumber yang sudah disetujui, dan hasilnya selalu berupa draf yang harus Anda setujui. Tanpa sumber, sistem menolak menulis.</p>
      <section className="grid gap-4"><h2 className="text-xl font-semibold">Gambar referensi kain</h2><p className="text-base">Gambar ini digunakan sebagai referensi budaya, bukan foto barang yang dijual.</p>{images.error && <Notice tone="error">{images.error}</Notice>}<div className="grid gap-4 sm:grid-cols-3">{images.data?.map((image) => <figure key={image.url} className="grid content-start gap-2"><img src={fileUrl(image.url)} alt={image.caption ?? e.name} className="aspect-square w-full object-cover" /><figcaption className="text-sm">{[image.caption, image.credit, image.license].filter(Boolean).join(" · ")}</figcaption>{image.id && <button className="link w-fit text-sm text-danger" disabled={act.busy} onClick={async () => { if (!window.confirm("Lepaskan gambar dari entri ini? File sumber tetap tersimpan.")) return; const result = await act.run(() => api(`/admin/gallery/${id}/images/${image.id}`, { method: "DELETE" })); if (result) images.reload(); }}>Lepaskan gambar</button>}</figure>)}</div><Field label="Keterangan gambar"><input className="field" value={caption} onChange={(event) => setCaption(event.target.value)} /></Field><Field label="Kredit"><input className="field" value={credit} onChange={(event) => setCredit(event.target.value)} /></Field><Field label="Lisensi"><input className="field" value={license} onChange={(event) => setLicense(event.target.value)} /></Field><Upload kind="reference_image" label="Unggah gambar referensi" accept="image/jpeg,image/png,image/webp" onUploaded={async (file) => { const result = await act.run(() => api(`/admin/gallery/${id}/images`, { body: { file_id: file.id, caption: caption || null, credit: credit || null, license: license || null } })); if (result) { setCaption(""); setCredit(""); setLicense(""); images.reload(); } }} /></section>
      <VariantManager entryId={id} />
      <h3 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Cerita</h3>
      <details className="rounded-xl bg-surface p-5"><summary className="cursor-pointer font-medium">Tulis draf cerita manual</summary><div className="mt-4 grid gap-4"><Field label="Cerita"><textarea className="field" value={storyBody} onChange={(event) => setStoryBody(event.target.value)} /></Field><fieldset className="grid gap-2"><legend>Sumber yang dikutip</legend>{sources.error && <Notice tone="error">{sources.error}</Notice>}{sources.data?.items.map((source) => <label key={source.id} className="flex items-center gap-2 text-base"><input type="checkbox" checked={sourceIds.includes(source.id)} onChange={(event) => setSourceIds(event.target.checked ? [...sourceIds, source.id] : sourceIds.filter((value) => value !== source.id))} />{source.title}</label>)}</fieldset><button className="btn w-fit" disabled={act.busy || !storyBody.trim() || sourceIds.length === 0} onClick={async () => { const result = await act.run(() => api(`/admin/gallery/${id}/stories`, { body: { body: storyBody, citations: sourceIds.map((source_id) => ({ source_id })), unresolved: [] } })); if (result) { setStoryBody(""); setSourceIds([]); stories.reload(); } }}>Simpan draf</button></div></details>
      <ul className="grid list-none gap-6 p-0">
        {stories.data?.map((s) => (
          <li key={s.id} className="grid gap-3 bg-surface p-5">
            <p className="text-base text-muted">Revisi {s.revision} · {STORY[s.status] ?? s.status} · {s.citations.length} kutipan</p>
            <div className="grid gap-2">{s.body.split("\n").map((p, i) => <p key={i}>{p}</p>)}</div>
            {s.unresolved.length > 0 && <ul className="list-disc pl-5 text-base">{s.unresolved.map((u) => <li key={u}>{u}</li>)}</ul>}
            {s.status === "draft" && <button className="btn w-fit" disabled={act.busy} onClick={() => go(() => api(`/admin/stories/${s.id}/submit`, { method: "POST" }))}>Ajukan untuk persetujuan</button>}
            {s.status === "in_review" && (
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
