"use client";

import Link from "next/link";
import { useState } from "react";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api } from "@/lib/api";
import type { Entry } from "@/lib/types";

function NewEntry({ onDone }: { onDone: () => void }) {
  const act = useAction();
  const [f, setF] = useState({ name: "", technique: "", region: "", community: "", summary: "" });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  return (
    <form className="grid max-w-2xl gap-4 bg-surface p-5" onSubmit={async (e) => { e.preventDefault(); const r = await act.run(() => api("/admin/gallery", { body: { ...f, kind: "tradition" } })); if (r) { setF({ name: "", technique: "", region: "", community: "", summary: "" }); onDone(); } }}>
      <h2 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Entri baru</h2>
      <Field label="Nama"><input className="field" required value={f.name} onChange={set("name")} /></Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Teknik"><input className="field" value={f.technique} onChange={set("technique")} /></Field>
        <Field label="Daerah"><input className="field" value={f.region} onChange={set("region")} /></Field>
        <Field label="Komunitas"><input className="field" value={f.community} onChange={set("community")} /></Field>
      </div>
      <Field label="Ringkasan"><textarea className="field" value={f.summary} onChange={set("summary")} /></Field>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <button className="btn w-fit" disabled={act.busy}>Buat entri (draf)</button>
    </form>
  );
}

function List() {
  const { data, error, loading, reload } = useLoad(() => api<{ items: Entry[] }>("/admin/gallery?limit=100"), "g");
  return (
    <div className="grid gap-10">
      {error && <Notice tone="error">{error}</Notice>}
      {loading ? <p>Memuat…</p> : (
        <ul className="grid max-w-3xl list-none gap-0 p-0">
          {data?.items.map((e) => (
            <li key={e.id}><Link href={`/admin/gallery/${e.id}`} className="group grid grid-cols-[1fr_auto] gap-x-6 py-4 no-underline"><span className="text-lg group-hover:underline underline-offset-4">{e.name}</span><span className="text-base">{{ draft: "Draf", published: "Terbit", archived: "Diarsipkan" }[e.status] ?? e.status}</span><span className="text-base text-muted">{e.region ?? "-"} · {e.technique ?? "-"}</span></Link></li>
          ))}
        </ul>
      )}
      <NewEntry onDone={reload} />
    </div>
  );
}

export default function AdminGalleryPage() {
  return (
    <Page>
      <p className="mb-2 mt-6 text-base"><Link href="/admin" className="link">← Admin</Link></p>
      <h1 className="t-head mb-10">Kurasi Gallery</h1>
      <RequireAuth role="admin"><List /></RequireAuth>
    </Page>
  );
}
