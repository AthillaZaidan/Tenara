"use client";

import Link from "next/link";
import { useState } from "react";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, when } from "@/lib/api";

type App = { id: string; type: string; status: string; data: Record<string, unknown>; submitted_at: string | null; decision_reason: string | null };

function Item({ a, reload }: { a: App; reload: () => void }) {
  const act = useAction();
  const [reason, setReason] = useState("");
  const send = async (action: string) => { const r = await act.run(() => api(`/admin/partner-applications/${a.id}/decision`, { body: { action, reason: reason || null } })); if (r) { setReason(""); reload(); } };
  const d = a.data as Record<string, string | string[] | undefined>;
  const closed = ["approved", "rejected"].includes(a.status);
  return (
    <li className="grid gap-3 bg-surface p-5">
      <h3 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>{String(d.shop_name ?? "Tanpa nama")} · {a.type === "merchant" ? "penjual" : "penjahit"}</h3>
      <p className="text-base">{[d.city, d.province].filter(Boolean).join(", ")} · {a.status.replaceAll("_", " ")} · {when(a.submitted_at)}</p>
      {d.description && <p className="text-base">{String(d.description)}</p>}
      <p className="text-base text-muted">Berkas bukti: {Array.isArray(d.evidence_file_ids) ? d.evidence_file_ids.length : 0}</p>
      {!closed && (
        <>
          <Field label="Alasan (wajib untuk menolak atau meminta informasi)"><input className="field" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
          {act.error && <Notice tone="error">{act.error}</Notice>}
          <div className="flex flex-wrap gap-3">
            {a.status === "submitted" && <button className="btn btn-quiet" disabled={act.busy} onClick={() => send("start_review")}>Mulai tinjau</button>}
            <button className="btn" disabled={act.busy} onClick={() => send("approve")}>Setujui</button>
            <button className="btn btn-quiet" disabled={act.busy || !reason.trim()} onClick={() => send("request_information")}>Minta informasi</button>
            <button className="btn btn-quiet" disabled={act.busy || !reason.trim()} onClick={() => send("reject")}>Tolak</button>
          </div>
        </>
      )}
      {a.decision_reason && <p className="text-base">Catatan: {a.decision_reason}</p>}
    </li>
  );
}

function List() {
  const { data, error, loading, reload } = useLoad(() => api<{ items: App[] }>("/admin/partner-applications"), "apps");
  return (
    <>
      {error && <Notice tone="error">{error}</Notice>}
      {loading ? <p>Memuat…</p> : data?.items.length === 0 ? <p>Belum ada pendaftaran.</p> : <ul className="grid max-w-3xl list-none gap-5 p-0">{data?.items.map((a) => <Item key={a.id} a={a} reload={reload} />)}</ul>}
    </>
  );
}

export default function AdminPartnersPage() {
  return (
    <Page>
      <p className="mb-2 mt-6 text-base"><Link href="/admin" className="link">← Admin</Link></p>
      <h1 className="t-head mb-10">Pendaftaran mitra</h1>
      <RequireAuth role="admin"><List /></RequireAuth>
    </Page>
  );
}
