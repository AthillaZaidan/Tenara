"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Chat } from "@/components/Chat";
import { Upload } from "@/components/Upload";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, idr, when } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Response = {
  id: string; kind: "discussion" | "proposal" | "rejection"; reason: string; buyer_decision: string; created_at: string;
  proposal: { remedy_type: string; amount_idr: number | null; description: string | null } | null;
};
type Claim = {
  id: string; order_id: string; status: string; target_role: string; component: string; description: string;
  conversation_id: string | null; evidence: { id: string; note: string | null }[]; responses: Response[];
  appeal: { id: string; status: string; reason: string } | null;
  decision: { outcome: string; remedy_type: string; amount_idr: number | null; reasoning: string; requires_execution: boolean } | null;
  remedy_events: { action: string; amount_idr: number | null; simulated: boolean; created_at: string }[];
  policy: { claim_window_ends_at: string | null; partner_response_due_at: string | null; partner_overdue: boolean; note: string } | null;
  roles: string[]; created_at: string; resolved_at: string | null; simulation_notice: string;
};

const STATUS: Record<string, string> = {
  opened: "Menunggu tanggapan", partner_discussion: "Dalam diskusi", resolution_proposed: "Ada tawaran penyelesaian",
  partner_rejected: "Ditolak mitra", appealed: "Banding diajukan", internal_review: "Ditinjau tim Tenara",
  decision_issued: "Keputusan terbit", resolved: "Selesai", withdrawn: "Ditarik",
};
const REMEDY: Record<string, string> = { none: "Tanpa kompensasi", explanation: "Penjelasan", rework: "Perbaikan", replacement: "Penggantian", refund_partial: "Pengembalian sebagian", refund_full: "Pengembalian penuh" };

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="grid gap-3"><h2 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>{title}</h2>{children}</section>;
}

function Detail() {
  const { id } = useParams<{ id: string }>();
  const { me } = useAuth();
  const { data: c, error, loading, reload } = useLoad(() => api<Claim>(`/claims/${id}`), id);
  const act = useAction();
  const [reason, setReason] = useState("");
  const [kind, setKind] = useState<"discussion" | "proposal" | "rejection">("discussion");
  const [remedy, setRemedy] = useState("explanation");
  const [amount, setAmount] = useState("");
  const [appealReason, setAppealReason] = useState("");

  if (loading) return <p>Memuat…</p>;
  if (error || !c) return <Notice tone="error">{error ?? "Klaim tidak ditemukan."}</Notice>;
  const buyer = c.roles.includes("buyer");
  const partner = c.roles.includes("merchant") || c.roles.includes("tailor");
  const done = ["resolved", "withdrawn"].includes(c.status);
  const rejection = [...c.responses].reverse().find((r) => r.kind === "rejection");
  const pending = c.responses.find((r) => r.kind === "proposal" && r.buyer_decision === "pending");
  const go = async <T,>(fn: () => Promise<T>) => { const r = await act.run(fn); if (r !== undefined) { setReason(""); setAppealReason(""); reload(); } };

  return (
    <div className="grid gap-12 md:grid-cols-12">
      <div className="grid content-start gap-10 md:col-span-7">
        <div>
          <p className="text-base text-muted">Klaim terhadap {c.target_role === "tailor" ? "penjahit" : "penjual"} · bagian {c.component} · {when(c.created_at)}</p>
          <h2 className="t-head" style={{ fontSize: "clamp(2rem, 1.3rem + 3.2vw, 3.5rem)" }}>{STATUS[c.status] ?? c.status}</h2>
          <p className="mt-4 max-w-[60ch]">{c.description}</p>
        </div>

        {c.policy && !done && (
          <p className="bg-surface p-4 text-base">
            {c.policy.partner_overdue ? "Batas tanggapan 48 jam sudah lewat." : `Mitra diminta menanggapi sebelum ${when(c.policy.partner_response_due_at)}.`} {c.policy.note}
          </p>
        )}
        {act.error && <Notice tone="error">{act.error}</Notice>}

        {c.responses.length > 0 && (
          <Block title="Tanggapan mitra">
            <ul className="grid list-none gap-4 p-0">
              {c.responses.map((r) => (
                <li key={r.id} className="grid gap-1 bg-surface p-4">
                  <span className="text-base text-muted">{{ discussion: "Diskusi", proposal: "Tawaran penyelesaian", rejection: "Penolakan" }[r.kind]} · {when(r.created_at)}</span>
                  <span>{r.reason}</span>
                  {r.proposal && <span className="text-base">{REMEDY[r.proposal.remedy_type]}{r.proposal.amount_idr ? ` · ${idr(r.proposal.amount_idr)}` : ""}{r.proposal.description ? ` · ${r.proposal.description}` : ""}</span>}
                  {r.kind === "proposal" && <span className="text-base text-muted">Keputusan pembeli: {{ pending: "menunggu", accepted: "diterima", rejected: "ditolak" }[r.buyer_decision] ?? r.buyer_decision}</span>}
                </li>
              ))}
            </ul>
          </Block>
        )}

        {buyer && pending && c.status === "resolution_proposed" && (
          <div className="flex flex-wrap gap-3">
            <button className="btn" disabled={act.busy} onClick={() => go(() => api(`/claims/${id}/proposals/${pending.id}/decision`, { body: { decision: "accept" } }))}>Terima tawaran</button>
            <button className="btn btn-quiet" disabled={act.busy} onClick={() => go(() => api(`/claims/${id}/proposals/${pending.id}/decision`, { body: { decision: "reject" } }))}>Tolak tawaran</button>
          </div>
        )}

        {buyer && c.status === "partner_rejected" && rejection && !c.appeal && (
          <Block title="Ajukan banding ke tim Tenara">
            <Field label="Alasan banding" hint="Minimal 5 karakter."><textarea className="field" value={appealReason} onChange={(e) => setAppealReason(e.target.value)} /></Field>
            <button className="btn w-fit" disabled={act.busy || appealReason.trim().length < 5} onClick={() => go(() => api(`/claims/${id}/appeals`, { body: { partner_rejection_id: rejection.id, reason: appealReason } }))}>Ajukan banding</button>
          </Block>
        )}
        {buyer && c.policy?.partner_overdue && ["opened", "partner_discussion"].includes(c.status) && !c.appeal && (
          <Block title="Mitra belum menanggapi">
            <p className="text-base">Karena batas waktu tanggapan lewat, Anda dapat meminta tim Tenara meninjau klaim ini.</p>
            <Field label="Alasan"><textarea className="field" value={appealReason} onChange={(e) => setAppealReason(e.target.value)} /></Field>
            <button className="btn w-fit" disabled={act.busy || appealReason.trim().length < 5} onClick={() => go(() => api(`/claims/${id}/escalate`, { body: { reason: appealReason } }))}>Minta tinjauan Tenara</button>
          </Block>
        )}

        {partner && !done && ["opened", "partner_discussion", "resolution_proposed"].includes(c.status) && (
          <Block title="Tanggapi klaim">
            <Field label="Jenis tanggapan">
              <select className="field" value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
                <option value="discussion">Diskusi / minta informasi</option>
                <option value="proposal">Tawarkan penyelesaian</option>
                <option value="rejection">Tolak klaim</option>
              </select>
            </Field>
            {kind === "proposal" && (
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Bentuk penyelesaian">
                  <select className="field" value={remedy} onChange={(e) => setRemedy(e.target.value)}>
                    {Object.entries(REMEDY).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </Field>
                {remedy.startsWith("refund") && <Field label="Jumlah (Rp)"><input className="field" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))} /></Field>}
              </div>
            )}
            <Field label="Penjelasan"><textarea className="field" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
            <button className="btn w-fit" disabled={act.busy || !reason.trim()} onClick={() => go(() => api(`/claims/${id}/responses`, { body: { kind, reason, proposal: kind === "proposal" ? { remedy_type: remedy, amount_idr: remedy.startsWith("refund") && amount ? Number(amount) : null, description: null } : null } }))}>Kirim tanggapan</button>
          </Block>
        )}

        {c.appeal && <Block title="Banding"><p>{c.appeal.reason}</p><p className="text-base text-muted">Status: {c.appeal.status}</p></Block>}
        {c.decision && (
          <Block title="Keputusan tim Tenara">
            <p className="text-lg">{{ upheld_rejection: "Penolakan mitra dipertahankan", overturned: "Penolakan dibatalkan", partial: "Dikabulkan sebagian" }[c.decision.outcome] ?? c.decision.outcome}</p>
            <p>{REMEDY[c.decision.remedy_type]}{c.decision.amount_idr ? ` · ${idr(c.decision.amount_idr)}` : ""}</p>
            <p className="max-w-[60ch]">{c.decision.reasoning}</p>
          </Block>
        )}
        {c.remedy_events.length > 0 && (
          <Block title="Pelaksanaan">
            <ul className="grid list-none gap-2 p-0 text-base">{c.remedy_events.map((r, i) => <li key={i}>{REMEDY[r.action]}{r.amount_idr ? ` · ${idr(r.amount_idr)}` : ""} · {when(r.created_at)}{r.simulated ? " · simulasi" : ""}</li>)}</ul>
          </Block>
        )}
      </div>

      <aside className="grid content-start gap-8 md:col-span-4 md:col-start-9">
        <Link href={`/orders/${c.order_id}`} className="link text-base">Lihat pesanan</Link>
        {buyer && !done && (
          <div className="grid gap-4">
            <Upload kind="claim_evidence" label="Tambah bukti" onUploaded={(f) => go(() => api(`/claims/${id}/evidence`, { body: { file_id: f.id, note: null } }))} />
            <button className="btn btn-quiet w-fit" disabled={act.busy} onClick={() => go(() => api(`/claims/${id}/withdraw`, { method: "POST" }))}>Tarik klaim</button>
          </div>
        )}
        <p className="text-base text-muted">Bukti terlampir: {c.evidence.length}</p>
        {c.conversation_id && me && (
          <div className="grid gap-3"><h2 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Percakapan klaim</h2><Chat conversationId={c.conversation_id} viewerId={me.id} /></div>
        )}
        <p className="t-small text-muted">{c.simulation_notice}</p>
      </aside>
    </div>
  );
}

export default function ClaimPage() {
  return (
    <Page>
      <p className="mb-2 mt-6 text-base"><Link href="/claims" className="link">← Semua klaim</Link></p>
      <RequireAuth><Detail /></RequireAuth>
    </Page>
  );
}
