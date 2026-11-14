"use client";

import Link from "next/link";
import { useState } from "react";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, fileUrl, when } from "@/lib/api";

type App = { id: string; type: string; status: string; applicant_id: string; data: Record<string, unknown>; submitted_at: string | null; decision_reason: string | null };
type Detail = { evidence: { file_id: string; content_type: string; url: string }[]; reviews: { action: string; reason: string | null; created_at: string }[] };

function Item({ a, reload }: { a: App; reload: () => void }) {
  const act = useAction();
  const [reason, setReason] = useState("");
  const [detail, setDetail] = useState<Detail | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const send = async (action: string) => { const r = await act.run(() => api(`/admin/partner-applications/${a.id}/decision`, { body: { action, reason: reason || null } })); if (r) { setReason(""); reload(); } };
  const d = a.data as Record<string, string | string[] | undefined>;
  const closed = ["approved", "rejected"].includes(a.status);
  return (
    <li className="grid gap-3 bg-surface p-5">
      <h3 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>{String(d.shop_name ?? "Tanpa nama")} · {a.type === "merchant" ? "penjual" : "penjahit"}</h3>
      <p className="text-base">{[d.city, d.province].filter(Boolean).join(", ")} · {a.status.replaceAll("_", " ")} · {when(a.submitted_at)}</p>
      {d.description && <p className="text-base">{String(d.description)}</p>}
      <p className="text-base text-muted">Berkas bukti: {Array.isArray(d.evidence_file_ids) ? d.evidence_file_ids.length : 0}</p>
      <button className="link w-fit text-base" disabled={act.busy} onClick={async () => { const result = await act.run(() => api<Detail>(`/admin/partner-applications/${a.id}`)); if (result) setDetail(result); }}>Lihat bukti dan riwayat</button>
      {detail && <div className="grid gap-2 text-base">{detail.evidence.map((file, i) => <a key={file.file_id} className="link w-fit" href={fileUrl(file.url)} target="_blank" rel="noreferrer">Berkas {i + 1} ({file.content_type})</a>)}<p className="text-muted">Tautan bukti berlaku sementara. Muat kembali jika kedaluwarsa.</p>{detail.reviews.map((review, index) => <p key={index}>{when(review.created_at)} · {review.action}{review.reason ? ` · ${review.reason}` : ""}</p>)}</div>}
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
      {a.status === "approved" && <details><summary className="cursor-pointer underline">Kelola status mitra</summary><div className="mt-3 grid gap-3"><Field label="Alasan (wajib untuk menangguhkan)"><input className="field" value={reason} onChange={(event) => setReason(event.target.value)} /></Field>{statusMessage && <Notice>{statusMessage}</Notice>}<div className="flex flex-wrap gap-3">{(["suspend", "reinstate"] as const).map((action) => <button key={action} className="btn btn-quiet" disabled={act.busy || (action === "suspend" && !reason.trim())} onClick={async () => { const result = await act.run(() => api(`/admin/partners/${action}`, { body: { user_id: a.applicant_id, role: a.type, reason: reason || null } })); if (result) setStatusMessage(action === "suspend" ? "Mitra ditangguhkan." : "Mitra diaktifkan kembali."); }}>{action === "suspend" ? "Tangguhkan" : "Aktifkan kembali"}</button>)}</div></div></details>}
      {closed && act.error && <Notice tone="error">{act.error}</Notice>}
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
