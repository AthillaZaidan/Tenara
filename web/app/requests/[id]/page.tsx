"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { MessageCircle, Package, Scissors, X } from "lucide-react";
import { Field, Notice, RequireAuth, useAction, useLoad } from "@/components/ui";
import { WorkspaceError, WorkspaceLoading, WorkspaceRoute } from "@/components/PartnerWorkspace";
import { api, fileUrl, idr, intentKey, when } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DIM_LABEL, OPTION_LABEL, REQUEST_STATUS, label, optionText } from "@/lib/design";

type Req = {
  id: string; status: string; revision: number; customization_id: string; tailor_id: string; reject_reason: string | null;
  address?: { id: string; recipient_name: string; line1: string; city: string; province: string };
  design_state?: Record<string, unknown>; measurements_cm?: Record<string, number>;
  estimate?: { required_length_cm?: number; purchase_quantity?: string; surplus_m?: string; fits?: boolean };
  template?: { code: string };
  design_preview?: { url: string; label: string } | null;
  requested_quantity?: string; required_continuous_cut_m?: number; selling_unit?: string;
};
type Quote = { id: string; revision: number; status: string; total_idr: number; expires_at: string; acceptable: boolean; lines: { kind: string; description: string; amount_idr: number }[] };

const H = { fontFamily: "var(--font-hanken)" } as const;
const Block = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="workspace-detail-card grid gap-4"><h2 className="text-xl font-medium" style={H}>{title}</h2>{children}</section>
);

function Buyer({ req, quotes, reload }: { req: Req; quotes: Quote[]; reload: () => void }) {
  const router = useRouter();
  const act = useAction();
  const [ack, setAck] = useState(false);
  const open = quotes.find((q) => q.status === "issued" && q.acceptable);
  const pay = async (q: Quote) => {
    const accepted = await act.run(() => api<{ payment: { id: string } }>(`/quotes/${q.id}/accept`, { body: { expected_quote_revision: q.revision, acknowledged_visual_reference: ack, delivery_address_id: req.address?.id ?? "" }, idempotencyKey: intentKey(`quote.${q.id}.${q.revision}.${req.address?.id ?? ""}`) }));
    if (!accepted) return;
    const paid = await act.run(() => api<{ order: { id: string } }>(`/demo-payments/${accepted.payment.id}/complete`, { body: { outcome: "succeeded" }, idempotencyKey: intentKey(`payment.${accepted.payment.id}.succeeded`) }));
    if (paid) router.push(`/orders/${paid.order.id}`);
  };
  return (
    <>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      {req.reject_reason && <Notice tone="error">{req.reject_reason}</Notice>}
      {req.status === "needs_revision" && <Link href={`/customize/${req.customization_id}`} className="btn w-fit no-underline">Revisi desain</Link>}
      {open && (
        <Block title="Penawaran dari penjahit">
          <ul className="grid list-none gap-2 p-0">{open.lines.map((l, i) => <li key={i} className="flex justify-between gap-4"><span>{l.description}</span><span>{idr(l.amount_idr)}</span></li>)}</ul>
          <p className="flex justify-between gap-4 bg-surface p-4 text-xl"><span>Total</span><span>{idr(open.total_idr)}</span></p>
          <p className="text-base text-muted">Berlaku sampai {when(open.expires_at)}. Pembayaran pada versi ini adalah simulasi.</p>
          <label className="flex items-start gap-3 text-base"><input type="checkbox" className="mt-1 size-5" checked={ack} onChange={(e) => setAck(e.target.checked)} /> Saya mengerti bahwa ilustrasi desain bersifat konseptual dan hasil jahitan dapat berbeda sedikit.</label>
          <button className="btn w-fit" disabled={act.busy || !ack} onClick={() => pay(open)}>Setujui dan bayar (simulasi)</button>
        </Block>
      )}
      {["draft", "submitted", "validating", "ready_for_quote", "awaiting_buyer", "needs_revision"].includes(req.status) && (
        <button className="btn btn-quiet w-fit" disabled={act.busy} onClick={async () => { const r = await act.run(() => api(`/custom-requests/${req.id}/withdraw`, { method: "POST" })); if (r) reload(); }}>Tarik permintaan</button>
      )}
    </>
  );
}

function Merchant({ req, reload }: { req: Req; reload: () => void }) {
  const act = useAction();
  const [reason, setReason] = useState("");
  if (req.status !== "submitted") return <Block title="Konfirmasi stok kain"><p className="text-base text-muted">Konfirmasi stok sudah diberikan atau tidak diperlukan pada tahap ini. Anda dapat mengikuti perkembangan melalui halaman pesanan.</p></Block>;
  return (
    <Block title="Konfirmasi stok kain">
      <p>Pembeli meminta {req.requested_quantity} {req.selling_unit === "meter" ? "m" : "potong"}{req.required_continuous_cut_m ? `, potongan utuh sekitar ${req.required_continuous_cut_m} m` : ""}. Data tubuh dan desain pembeli tidak ditampilkan kepada penjual.</p>
      <Field label="Alasan jika menolak"><input className="field" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <div className="flex gap-3">
        <button className="btn" disabled={act.busy} onClick={async () => { const r = await act.run(() => api(`/custom-requests/${req.id}/merchant-confirmation`, { body: { decision: "confirm" } })); if (r) reload(); }}>Stok tersedia</button>
        <button className="btn btn-quiet" disabled={act.busy || !reason.trim()} onClick={async () => { const r = await act.run(() => api(`/custom-requests/${req.id}/merchant-confirmation`, { body: { decision: "reject", reason } })); if (r) reload(); }}>Tidak tersedia</button>
      </div>
    </Block>
  );
}

function Tailor({ req, quotes, reload }: { req: Req; quotes: Quote[]; reload: () => void }) {
  const act = useAction();
  const [reason, setReason] = useState("");
  const [qty, setQty] = useState(req.estimate?.purchase_quantity ?? "");
  const [lead, setLead] = useState("14");
  const [dims, setDims] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState("");
  const [sur, setSur] = useState<{ description: string; amount: string }[]>([]);
  const [mat, setMat] = useState<{ name: string; provider: "tailor" | "merchant"; price: string }[]>([]);
  const [specId, setSpecId] = useState<string | null>(null);
  const dimKeys = ["chest_width", "length"];
  const canSpec = ["validating", "ready_for_quote", "awaiting_buyer"].includes(req.status);
  const issue = async (id: string) => { const q = await act.run(() => api(`/custom-requests/${req.id}/quotes`, { body: { spec_id: id } })); if (q) reload(); };
  return (
    <>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      {["submitted", "validating", "ready_for_quote", "awaiting_buyer"].includes(req.status) && (
        <Block title="Keputusan penjahit">
          <p className="text-base text-muted">Tinjau detail rancangan sebelum melanjutkan. Jika ada yang perlu disesuaikan, sampaikan alasannya kepada pembeli.</p>
          <Field label="Alasan (wajib untuk meminta revisi atau menolak)"><input className="field" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
          <div className="flex flex-wrap gap-3">
            <button className="btn btn-quiet" disabled={act.busy || !reason.trim()} onClick={async () => { const r = await act.run(() => api(`/custom-requests/${req.id}/tailor-decision`, { body: { action: "return_for_revision", reason } })); if (r) reload(); }}>Minta revisi desain</button>
            <button className="btn btn-quiet" disabled={act.busy || !reason.trim()} onClick={async () => { const r = await act.run(() => api(`/custom-requests/${req.id}/tailor-decision`, { body: { action: "reject", reason } })); if (r) reload(); }}>Tolak</button>
          </div>
        </Block>
      )}
      {canSpec && (
        <Block title="Spesifikasi produksi dan penawaran">
          <p className="text-base text-muted">Tentukan kebutuhan kain, ukuran jadi, dan waktu pengerjaan sebagai dasar penawaran Anda.</p>
          <div className="workspace-form-grid grid gap-4 sm:grid-cols-2">
            <Field label="Kain yang dibeli (m / potong)"><input className="field" inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} /></Field>
            <Field label="Lama pengerjaan (hari)"><input className="field" inputMode="numeric" value={lead} onChange={(e) => setLead(e.target.value)} /></Field>
            {dimKeys.map((k) => <Field key={k} label={`Ukuran jadi: ${k === "chest_width" ? "lebar dada" : "panjang"} (cm)`}><input className="field" inputMode="decimal" value={dims[k] ?? ""} onChange={(e) => setDims({ ...dims, [k]: e.target.value })} /></Field>)}
          </div>
          <Field label="Catatan motif"><input className="field" value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
          <div className="grid gap-2">
            <p className="text-base">Biaya tambahan</p>
            {sur.map((s, i) => (
              <div key={i} className="workspace-repeat-row grid gap-3">
                <div className="workspace-form-grid">
                <input className="field" placeholder="Deskripsi" aria-label="Deskripsi biaya" value={s.description} onChange={(e) => setSur(sur.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)))} />
                <input className="field" placeholder="Rp" aria-label="Jumlah biaya" inputMode="numeric" value={s.amount} onChange={(e) => setSur(sur.map((x, j) => (j === i ? { ...x, amount: e.target.value.replace(/\D/g, "") } : x)))} />
                </div><button type="button" className="workspace-link justify-self-start" aria-label={`Hapus biaya tambahan ${i + 1}`} onClick={() => setSur(sur.filter((_, j) => j !== i))}><X size={13} />Hapus biaya</button>
              </div>
            ))}
            <button type="button" className="btn btn-quiet w-fit" onClick={() => setSur([...sur, { description: "", amount: "" }])}>Tambah biaya</button>
          </div>
          <div className="grid gap-2">
            <p className="text-base">Bahan tambahan</p>
            {mat.map((m, i) => (
              <div key={i} className="workspace-repeat-row grid gap-3">
                <input className="field" placeholder="Nama bahan" aria-label="Nama bahan" value={m.name} onChange={(e) => setMat(mat.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} />
                <div className="workspace-form-grid"><select className="field" aria-label="Penyedia" value={m.provider} onChange={(e) => setMat(mat.map((x, j) => (j === i ? { ...x, provider: e.target.value as "tailor" | "merchant" } : x)))}><option value="tailor">Penjahit</option><option value="merchant">Penjual</option></select>
                <input className="field" placeholder="Rp" aria-label="Harga bahan" inputMode="numeric" value={m.price} onChange={(e) => setMat(mat.map((x, j) => (j === i ? { ...x, price: e.target.value.replace(/\D/g, "") } : x)))} />
                </div><button type="button" className="workspace-link justify-self-start" aria-label={`Hapus bahan tambahan ${i + 1}`} onClick={() => setMat(mat.filter((_, j) => j !== i))}><X size={13} />Hapus bahan</button>
              </div>
            ))}
            <button type="button" className="btn btn-quiet w-fit" onClick={() => setMat([...mat, { name: "", provider: "tailor", price: "" }])}>Tambah bahan</button>
          </div>
          <div className="flex flex-wrap gap-3">
            <button className="btn" disabled={act.busy || !qty || dimKeys.some((k) => !dims[k])} onClick={async () => {
              const spec = await act.run(() => api<{ id: string }>(`/custom-requests/${req.id}/production-spec`, { body: {
                fabric_purchase_quantity: qty, lead_time_days: Number(lead) || 1, motif_notes: notes || null,
                finished_dimensions: Object.fromEntries(dimKeys.map((k) => [k, Number(dims[k])])),
                surcharges: sur.filter((s) => s.description && s.amount).map((s) => ({ description: s.description, amount_idr: Number(s.amount) })),
                extra_materials: mat.filter((m) => m.name).map((m) => ({ name: m.name, provider: m.provider, price_idr: Number(m.price || 0) })),
              } }));
              if (spec) { setSpecId(spec.id); reload(); }
            }}>{act.busy ? "Memproses…" : "Terbitkan spesifikasi"}</button>
            {specId && <button className="btn btn-quiet" disabled={act.busy} onClick={() => issue(specId)}>Terbitkan penawaran</button>}
          </div>
        </Block>
      )}
      {quotes.length > 0 && <p className="text-base text-muted">Penawaran terakhir: {idr(quotes[0].total_idr)} ({{ issued: "Terbit", accepted: "Disetujui", expired: "Kedaluwarsa", withdrawn: "Ditarik" }[quotes[0].status] ?? quotes[0].status}).</p>}
    </>
  );
}

function Detail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const chatAction = useAction();
  const { has } = useAuth();
  const roles = (["buyer", "merchant", "tailor"] as const).filter((r) => has(r));
  const asParam = useSearchParams().get("as");
  const role = roles.find((r) => r === asParam) ?? roles[0] ?? "buyer";
  const { data: req, error, loading, reload } = useLoad(() => api<Req>(`/custom-requests/${id}`), `${id}-${role}`);
  const quotes = useLoad(() => api<Quote[]>(`/custom-requests/${id}/quotes`).catch(() => [] as Quote[]), `${id}-${req?.status ?? ""}`);
  if (loading) return <WorkspaceLoading>Memuat detail permintaan…</WorkspaceLoading>;
  if (error || !req) return <WorkspaceError message={error ?? "Permintaan tidak ditemukan."} retry={reload} />;
  return (
    <div className="workspace-detail workspace-request-detail grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="workspace-detail-main grid content-start gap-6">
        <div className="workspace-detail-hero">
          <p className="text-base text-muted">Permintaan baju · revisi {req.revision}</p>
          <h2 className="workspace-detail-title t-statement">{REQUEST_STATUS[req.status] ?? req.status}</h2>
          <span className="workspace-id">ID permintaan · {req.id}</span>
        </div>
        {chatAction.error && <Notice tone="error">{chatAction.error}</Notice>}
        <div className="flex flex-wrap gap-3">{(role === "buyer" ? ["merchant", "tailor"] : [role]).map((partner) => <button key={partner} className="btn btn-quiet" disabled={chatAction.busy} onClick={async () => {
          const conversation = await chatAction.run(() => api<{ id: string }>("/conversations", { body: { request_id: id, with: partner } }));
          if (conversation) router.push(`/messages/${conversation.id}?as=${role}`);
        }}><MessageCircle size={15} />Chat {role === "buyer" ? partner === "merchant" ? "penjual" : "penjahit" : "pembeli"}</button>)}</div>
        {role === "buyer" && <Buyer req={req} quotes={quotes.data ?? []} reload={() => { reload(); quotes.reload(); }} />}
        {role === "merchant" && <Merchant req={req} reload={reload} />}
        {role === "tailor" && <Tailor req={req} quotes={quotes.data ?? []} reload={() => { reload(); quotes.reload(); }} />}
      </div>
      <aside className="workspace-detail-aside grid content-start gap-6">
        {req.design_preview?.url && role !== "merchant" && (
          <figure className="workspace-detail-card m-0 grid gap-2">
            <img src={fileUrl(req.design_preview.url)} alt="Ilustrasi konseptual desain" className="w-full bg-surface" />
            <figcaption className="text-base text-muted">{req.design_preview.label}</figcaption>
          </figure>
        )}
        {req.design_state && role !== "merchant" && (
          <section className="workspace-detail-card grid gap-3 text-base">
            <h2 className="flex items-center gap-2"><Scissors size={16} strokeWidth={1.5} />Detail rancangan</h2>
            {Object.entries(req.design_state).map(([k, v]) => <p key={k} className="flex justify-between gap-4"><span className="text-muted">{label(OPTION_LABEL, k)}</span><span>{optionText(v)}</span></p>)}
          </section>
        )}
        {req.measurements_cm && role !== "merchant" && (
          <section className="workspace-detail-card grid gap-3 text-base">
            <h2>Ukuran tubuh (cm)</h2>
            {Object.entries(req.measurements_cm).map(([k, v]) => <p key={k} className="flex justify-between gap-4"><span className="text-muted">{label(DIM_LABEL, k)}</span><span>{v}</span></p>)}
          </section>
        )}
        <section className="workspace-detail-card grid gap-3"><h2 className="flex items-center gap-2"><Package size={16} strokeWidth={1.5} />Kebutuhan kain</h2><dl className="workspace-key-values"><div><dt>Jumlah</dt><dd>{req.estimate?.purchase_quantity ?? req.requested_quantity ?? "—"} {req.selling_unit === "piece" ? "potong" : "m"}</dd></div>{req.required_continuous_cut_m && <div><dt>Potongan utuh</dt><dd>{req.required_continuous_cut_m} m</dd></div>}{req.estimate?.surplus_m && <div><dt>Estimasi sisa</dt><dd>{req.estimate.surplus_m} m</dd></div>}</dl></section>
        {req.address && role !== "merchant" && <section className="workspace-detail-card"><h2>Tujuan pengiriman</h2><p className="text-base text-muted">{req.address.city}, {req.address.province}</p></section>}
      </aside>
    </div>
  );
}

export default function RequestPage() {
  return (
    <Suspense fallback={<WorkspaceLoading />}><RequireAuth><WorkspaceRoute active="requests" title="Detail permintaan" description="Tinjau kebutuhan pembeli dan susun langkah untuk mewujudkannya." back={{ href: "/requests", label: "Permintaan baju" }}><Detail /></WorkspaceRoute></RequireAuth></Suspense>
  );
}
