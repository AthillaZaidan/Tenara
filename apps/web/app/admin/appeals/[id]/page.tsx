"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, idr, when } from "@/lib/api";

type Bundle = {
  appeal: { id: string; status: string; basis: string; claim_id: string; reason: string };
  claim: { id: string; status: string; description: string; component: string; target_role: string; decision: { outcome: string; remedy_type: string; amount_idr: number | null; reasoning: string; requires_execution: boolean } | null; responses?: { kind: string; reason: string }[] };
  order: { id: string; kind: string; status: string; total_idr: number };
  order_events: { type: string; to: string; at: string; note: string | null }[];
  inspections: { passed: boolean; condition: string; notes: string | null }[];
  claim_messages: { id: string; body: string; created_at: string }[];
};
const REMEDY = ["none", "explanation", "rework", "replacement", "refund_partial", "refund_full"];

function Review() {
  const { id } = useParams<{ id: string }>();
  const { data: b, error, loading, reload } = useLoad(() => api<Bundle>(`/admin/appeals/${id}`), id);
  const act = useAction();
  const [outcome, setOutcome] = useState("overturned");
  const [remedy, setRemedy] = useState("explanation");
  const [amount, setAmount] = useState("");
  const [reasoning, setReasoning] = useState("");
  const [ask, setAsk] = useState("");
  const go = async <T,>(fn: () => Promise<T>) => { const r = await act.run(fn); if (r !== undefined) reload(); };
  if (loading) return <p>Memuat…</p>;
  if (error || !b) return <Notice tone="error">{error ?? "Banding tidak ditemukan."}</Notice>;
  const decided = b.appeal.status === "decided";
  const needsExec = b.claim.decision?.requires_execution && b.claim.status === "decision_issued";
  return (
    <div className="grid gap-12 md:grid-cols-12">
      <div className="grid content-start gap-8 md:col-span-7">
        <div>
          <p className="text-base text-muted">{b.appeal.basis === "no_response" ? "Mitra tidak menanggapi dalam batas waktu" : "Penolakan mitra dibanding"} · status {b.appeal.status.replaceAll("_", " ")}</p>
          <h1 className="t-head" style={{ fontSize: "clamp(2rem, 1.3rem + 3.2vw, 3.5rem)" }}>Klaim {b.claim.component}</h1>
          <p className="mt-3 max-w-[60ch]">{b.claim.description}</p>
          <p className="mt-3 max-w-[60ch]"><span className="text-muted">Alasan banding: </span>{b.appeal.reason}</p>
        </div>
        {act.error && <Notice tone="error">{act.error}</Notice>}
        {b.appeal.status === "open" && <button className="btn w-fit" disabled={act.busy} onClick={() => go(() => api(`/admin/appeals/${id}/start-review`, { method: "POST" }))}>Mulai tinjau</button>}
        {!decided && b.appeal.status !== "open" && (
          <>
            <section className="grid gap-3">
              <h3 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Minta bukti tambahan</h3>
              <Field label="Pesan ke pihak terkait"><input className="field" value={ask} onChange={(e) => setAsk(e.target.value)} /></Field>
              <button className="btn btn-quiet w-fit" disabled={act.busy || !ask.trim()} onClick={() => go(() => api(`/admin/appeals/${id}/request-evidence`, { body: { message: ask } }).then((r) => { setAsk(""); return r; }))}>Kirim permintaan</button>
            </section>
            <section className="grid gap-4">
              <h3 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Putusan</h3>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Hasil"><select className="field" value={outcome} onChange={(e) => setOutcome(e.target.value)}><option value="upheld_rejection">Penolakan dipertahankan</option><option value="overturned">Penolakan dibatalkan</option><option value="partial">Dikabulkan sebagian</option></select></Field>
                <Field label="Bentuk penyelesaian"><select className="field" value={remedy} onChange={(e) => setRemedy(e.target.value)}>{REMEDY.map((r) => <option key={r} value={r}>{r.replaceAll("_", " ")}</option>)}</select></Field>
                {remedy.startsWith("refund") && <Field label="Jumlah (Rp)"><input className="field" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))} /></Field>}
              </div>
              <Field label="Alasan putusan" hint="Minimal 5 karakter; dilihat kedua pihak."><textarea className="field" value={reasoning} onChange={(e) => setReasoning(e.target.value)} /></Field>
              <button className="btn w-fit" disabled={act.busy || reasoning.trim().length < 5} onClick={() => go(() => api(`/appeals/${id}/decision`, { body: { outcome, remedy_type: remedy, amount_idr: remedy.startsWith("refund") && amount ? Number(amount) : null, reasoning } }))}>Terbitkan putusan</button>
            </section>
          </>
        )}
        {b.claim.decision && (
          <section className="grid gap-3 bg-surface p-5">
            <h3 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Putusan terbit</h3>
            <p>{b.claim.decision.outcome.replaceAll("_", " ")} · {b.claim.decision.remedy_type.replaceAll("_", " ")}{b.claim.decision.amount_idr ? ` · ${idr(b.claim.decision.amount_idr)}` : ""}</p>
            <p className="text-base">{b.claim.decision.reasoning}</p>
            {needsExec && (
              <div className="grid gap-2">
                <p className="text-base text-muted">Pelaksanaan dicatat terpisah dari putusan dan bersifat simulasi di versi ini.</p>
                <button className="btn w-fit" disabled={act.busy} onClick={() => go(() => api(`/claims/${b.claim.id}/remedy-events`, { body: { action: b.claim.decision!.remedy_type, amount_idr: b.claim.decision!.amount_idr, note: null } }))}>Catat pelaksanaan (simulasi)</button>
              </div>
            )}
          </section>
        )}
      </div>
      <aside className="grid content-start gap-6 md:col-span-4 md:col-start-9">
        <div className="grid gap-1 bg-surface p-5 text-base"><h3 className="mb-1 text-lg font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Pesanan</h3><p>{b.order.kind === "custom" ? "Baju custom" : "Kain"} · {b.order.status.replaceAll("_", " ")} · {idr(b.order.total_idr)}</p></div>
        <div className="text-base"><h3 className="mb-2 text-lg font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Riwayat</h3><ul className="grid list-none gap-1 p-0">{b.order_events.map((e, i) => <li key={i}>{e.to.replaceAll("_", " ")} <span className="text-muted">· {when(e.at)}</span></li>)}</ul></div>
        {b.inspections.length > 0 && <div className="text-base"><h3 className="mb-2 text-lg font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Pemeriksaan kain</h3>{b.inspections.map((i, k) => <p key={k}>{i.passed ? "Lolos" : "Bermasalah"} · {i.condition}</p>)}</div>}
        {b.claim_messages.length > 0 && <div className="text-base"><h3 className="mb-2 text-lg font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Percakapan klaim</h3><ul className="grid list-none gap-2 p-0">{b.claim_messages.map((m) => <li key={m.id}>{m.body}</li>)}</ul></div>}
        <Link href={`/claims/${b.claim.id}`} className="link text-base">Buka halaman klaim</Link>
      </aside>
    </div>
  );
}

export default function AdminAppealPage() {
  return (
    <Page>
      <p className="mb-2 mt-6 text-base"><Link href="/admin/appeals" className="link">← Banding</Link></p>
      <RequireAuth role="admin"><Review /></RequireAuth>
    </Page>
  );
}
