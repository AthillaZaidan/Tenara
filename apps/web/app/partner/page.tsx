"use client";

import { useState } from "react";
import { Upload, type Uploaded } from "@/components/Upload";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, when } from "@/lib/api";

type App = { id: string; type: "merchant" | "tailor"; status: string; data: Record<string, unknown>; decision_reason?: string | null; submitted_at?: string | null };

const STATUS: Record<string, string> = { draft: "Draf", submitted: "Diajukan, menunggu tinjauan", in_review: "Sedang ditinjau", information_requested: "Perlu informasi tambahan", approved: "Disetujui", rejected: "Ditolak" };

function Form() {
  const mine = useLoad(() => api<App[]>("/partner-applications/mine"), "mine");
  const act = useAction();
  const [type, setType] = useState<"merchant" | "tailor">("merchant");
  const [f, setF] = useState({ shop_name: "", description: "", city: "", province: "", contact_phone: "", experience_years: "" });
  const [files, setFiles] = useState<Uploaded[]>([]);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });
  const open = (mine.data ?? []).find((a) => ["draft", "submitted", "in_review", "information_requested"].includes(a.status));

  if (mine.loading) return <p>Memuat…</p>;
  return (
    <div className="grid max-w-2xl gap-10">
      {(mine.data ?? []).length > 0 && (
        <ul className="grid list-none gap-3 p-0">
          {mine.data!.map((a) => (
            <li key={a.id} className="grid gap-1 bg-surface p-4">
              <span className="text-lg">{a.type === "merchant" ? "Penjual kain" : "Penjahit"}: {STATUS[a.status] ?? a.status}</span>
              {a.submitted_at && <span className="text-base text-muted">Diajukan {when(a.submitted_at)}</span>}
              {a.decision_reason && <span className="text-base">{a.decision_reason}</span>}
            </li>
          ))}
        </ul>
      )}
      {!open && (
        <form
          className="grid gap-5"
          onSubmit={async (e) => {
            e.preventDefault();
            const done = await act.run(async () => {
              const data = { ...f, experience_years: f.experience_years ? Number(f.experience_years) : undefined, evidence_file_ids: files.map((x) => x.id) };
              const created = await api<{ id: string }>("/partner-applications", { body: { type, data } });
              await api(`/partner-applications/${created.id}/submit`, { method: "POST" });
              return created;
            });
            if (done) mine.reload();
          }}
        >
          <Field label="Mendaftar sebagai">
            <select className="field" value={type} onChange={(e) => setType(e.target.value as typeof type)}>
              <option value="merchant">Penjual kain</option>
              <option value="tailor">Penjahit</option>
            </select>
          </Field>
          <Field label="Nama usaha"><input className="field" required value={f.shop_name} onChange={set("shop_name")} /></Field>
          <Field label="Tentang usaha"><textarea className="field" value={f.description} onChange={set("description")} /></Field>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Kota"><input className="field" required value={f.city} onChange={set("city")} /></Field>
            <Field label="Provinsi"><input className="field" required value={f.province} onChange={set("province")} /></Field>
            <Field label="Telepon"><input className="field" value={f.contact_phone} onChange={set("contact_phone")} /></Field>
            {type === "tailor" && <Field label="Pengalaman (tahun)"><input className="field" inputMode="numeric" value={f.experience_years} onChange={set("experience_years")} /></Field>}
          </div>
          <Upload kind="verification_doc" label="Dokumen atau foto usaha untuk verifikasi (privat, hanya dilihat tim Tenara)" onUploaded={(u) => setFiles((p) => [...p, u])} />
          {files.length > 0 && <p className="text-base">{files.length} berkas terlampir.</p>}
          {act.error && <Notice tone="error">{act.error}</Notice>}
          <button className="btn w-fit" disabled={act.busy}>Ajukan pendaftaran</button>
          <p className="t-small text-muted">Verifikasi mitra menandakan usaha ini dikenal platform. Ini bukan sertifikasi keaslian atau asal-usul kain tertentu.</p>
        </form>
      )}
    </div>
  );
}

export default function PartnerPage() {
  return (
    <Page>
      <h1 className="t-display mb-10 mt-8" style={{ fontSize: "clamp(40px, 7vw, 112px)" }}>Jadi mitra</h1>
      <RequireAuth><Form /></RequireAuth>
    </Page>
  );
}
