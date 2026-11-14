"use client";

import Link from "next/link";
import { useState } from "react";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api } from "@/lib/api";
import type { Entry } from "@/lib/types";

type Source = { id: string; title: string; publisher: string | null; url: string | null; license: string | null; rights_notes: string | null; approval_status: string; decision_reason: string | null };

const STATUS: Record<string, string> = { pending: "Menunggu tinjauan", approved: "Disetujui", rejected: "Ditolak" };

function Row({ s, onDone, entries }: { s: Source; onDone: () => void; entries: Entry[] }) {
  const act = useAction();
  const [reason, setReason] = useState("");
  const [text, setText] = useState("");
  const [locator, setLocator] = useState("");
  const [entryId, setEntryId] = useState("");
  const [added, setAdded] = useState(false);
  const links = (s.rights_notes ?? "").split("\n").filter((l) => l.startsWith("- "));
  const decide = async (decision: "approve" | "reject") => {
    const r = await act.run(() => api(`/admin/sources/${s.id}/decision`, { body: { decision, reason: reason || null } }));
    if (r) onDone();
  };
  return (
    <li className="grid gap-3 bg-surface p-5">
      <h3 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>{s.title}</h3>
      <p className="text-base text-muted">{[s.publisher, s.license, STATUS[s.approval_status]].filter(Boolean).join(" · ")}</p>
      {links.length > 0 && (
        <ul className="grid list-none gap-1 p-0 text-base">
          {links.map((l) => {
            const m = l.match(/^- (.*): (https?:\/\/\S+)$/);
            return <li key={l}>{m ? <a href={m[2]} target="_blank" rel="noopener noreferrer" className="link">{m[1]}</a> : l.slice(2)}</li>;
          })}
        </ul>
      )}
      {s.approval_status === "pending" && (
        <>
          <Field label="Catatan (wajib untuk menolak)"><input className="field" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
          {act.error && <Notice tone="error">{act.error}</Notice>}
          <div className="flex flex-wrap gap-3">
            <button className="btn" disabled={act.busy} onClick={() => decide("approve")}>Setujui</button>
            <button className="btn btn-quiet" disabled={act.busy || !reason.trim()} onClick={() => decide("reject")}>Tolak</button>
          </div>
        </>
      )}
      {s.decision_reason && <p className="text-base">Catatan: {s.decision_reason}</p>}
      <details><summary className="cursor-pointer underline">Tambah potongan sumber</summary><div className="mt-4 grid gap-4">
        <Field label="Teks kutipan"><textarea className="field" value={text} onChange={(event) => setText(event.target.value)} /></Field>
        <Field label="Lokasi dalam sumber (opsional)"><input className="field" value={locator} onChange={(event) => setLocator(event.target.value)} placeholder="Halaman atau bagian" /></Field>
        <Field label="Entri kain (opsional)"><select className="field" value={entryId} onChange={(event) => setEntryId(event.target.value)}><option value="">Tidak ditentukan</option>{entries.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select></Field>
        {act.error && <Notice tone="error">{act.error}</Notice>}{added && <Notice>Potongan sumber disimpan.</Notice>}
        <button className="btn w-fit" disabled={act.busy || !text.trim()} onClick={async () => { const result = await act.run(() => api(`/admin/sources/${s.id}/chunks`, { body: { text, locator: locator || null, entry_id: entryId || null } })); if (result) { setText(""); setLocator(""); setAdded(true); } }}>Simpan potongan</button>
      </div></details>
    </li>
  );
}

function List() {
  const [status, setStatus] = useState("pending");
  const { data, error, loading, reload } = useLoad(() => api<{ items: Source[] }>(`/admin/sources?approval_status=${status}&limit=100`), status);
  const act = useAction();
  const entries = useLoad(() => api<{ items: Entry[] }>("/admin/gallery?limit=100"), "entries");
  const [source, setSource] = useState({ title: "", publisher: "", url: "", license: "", rights_notes: "" });
  const pending = (data?.items ?? []).filter((s) => s.approval_status === "pending");
  return (
    <div className="grid gap-8">
      <p className="max-w-[64ch]">Sumber yang disetujui di sini dipakai untuk mencocokkan scan kain dan menulis cerita. Dossier riset web disusun otomatis oleh AI dari sumber yang tercantum; periksa tautannya sebelum menyetujui.</p>
      <details className="max-w-3xl rounded-xl bg-surface p-5"><summary className="cursor-pointer font-medium">Tambah sumber budaya</summary><div className="mt-4 grid gap-4">{([ ["title", "Judul"], ["publisher", "Penerbit"], ["url", "URL"], ["license", "Lisensi"], ["rights_notes", "Catatan hak penggunaan"] ] as const).map(([key, label]) => <Field key={key} label={label}><input className="field" value={source[key]} onChange={(event) => setSource({ ...source, [key]: event.target.value })} /></Field>)}<button className="btn w-fit" disabled={act.busy || !source.title.trim()} onClick={async () => { const result = await act.run(() => api("/admin/sources", { body: { title: source.title, publisher: source.publisher || null, url: source.url || null, license: source.license || null, rights_notes: source.rights_notes || null } })); if (result) { setSource({ title: "", publisher: "", url: "", license: "", rights_notes: "" }); setStatus("pending"); reload(); } }}>Simpan sumber</button></div></details>
      {entries.error && <Notice tone="error">Daftar entri tidak dapat dimuat: {entries.error}</Notice>}
      <p className="flex flex-wrap gap-4 text-base">
        {Object.entries(STATUS).map(([k, v]) => <button key={k} onClick={() => setStatus(k)} className={k === status ? "link font-medium" : "cursor-pointer hover:underline underline-offset-4"}>{v}</button>)}
      </p>
      {error && <Notice tone="error">{error}</Notice>}
      {act.error && <Notice tone="error">{act.error}</Notice>}
      {status === "pending" && pending.length > 1 && (
        <button className="btn w-fit" disabled={act.busy} onClick={async () => {
          if (!window.confirm(`Setujui ${pending.length} sumber sekaligus? Pastikan Anda sudah meninjaunya.`)) return;
          await act.run(async () => { for (const s of pending) await api(`/admin/sources/${s.id}/decision`, { body: { decision: "approve", reason: "Ditinjau kurator (persetujuan massal)" } }); return true; });
          reload();
        }}>Setujui semua yang tampil ({pending.length})</button>
      )}
      {loading ? <p>Memuat…</p> : data?.items.length === 0 ? <p>Tidak ada sumber di status ini.</p> : (
        <ul className="grid max-w-3xl list-none gap-5 p-0">{data?.items.map((s) => <Row key={s.id} s={s} onDone={reload} entries={entries.data?.items ?? []} />)}</ul>
      )}
    </div>
  );
}

export default function AdminSourcesPage() {
  return (
    <Page>
      <p className="mb-2 mt-6 text-base"><Link href="/admin" className="link">← Admin</Link></p>
      <h1 className="t-head mb-10">Sumber budaya</h1>
      <RequireAuth role="admin"><List /></RequireAuth>
    </Page>
  );
}
