"use client";

import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, idr, newKey, when } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DIM_LABEL, OPTION_LABEL, REQUEST_STATUS, VALUE_LABEL, label } from "@/lib/design";

type Req = {
  id: string; status: string; revision: number; customization_id: string; tailor_id: string; reject_reason: string | null;
  address?: { id: string; recipient_name: string; line1: string; city: string; province: string };
  design_state?: Record<string, string | number>; measurements_cm?: Record<string, number>;
  estimate?: { required_length_cm?: number; purchase_quantity?: string; surplus_m?: string; fits?: boolean };
  template?: { code: string };
  requested_quantity?: string; required_continuous_cut_m?: number; selling_unit?: string;
};
type Quote = { id: string; revision: number; status: string; total_idr: number; expires_at: string; acceptable: boolean; lines: { kind: string; description: string; amount_idr: number }[] };

const H = { fontFamily: "var(--font-hanken)" } as const;
const Block = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="grid gap-4"><h2 className="text-xl font-medium" style={H}>{title}</h2>{children}</section>
);

function Buyer({ req, quotes, reload }: { req: Req; quotes: Quote[]; reload: () => void }) {
  const router = useRouter();
  const act = useAction();
  const [ack, setAck] = useState(false);
  const open = quotes.find((q) => q.status === "issued" && q.acceptable);
  const pay = async (q: Quote) => {
    const accepted = await act.run(() => api<{ payment: { id: string } }>(`/quotes/${q.id}/accept`, { body: { expected_quote_revision: q.revision, acknowledged_visual_reference: ack, delivery_address_id: req.address?.id ?? "" }, idempotencyKey: newKey() }));
    if (!accepted) return;
    const paid = await act.run(() => api<{ order: { id: string } }>(`/demo-payments/${accepted.payment.id}/complete`, { body: { outcome: "succeeded" }, idempotencyKey: newKey() }));
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
  if (req.status !== "submitted") return <p>Konfirmasi stok sudah diberikan atau tidak diperlukan.</p>;
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
          <Field label="Alasan (wajib untuk meminta revisi atau menolak)"><input className="field" value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
          <div className="flex flex-wrap gap-3">
            <button className="btn btn-quiet" disabled={act.busy || !reason.trim()} onClick={async () => { const r = await act.run(() => api(`/custom-requests/${req.id}/tailor-decision`, { body: { action: "return_for_revision", reason } })); if (r) reload(); }}>Minta revisi desain</button>
            <button className="btn btn-quiet" disabled={act.busy || !reason.trim()} onClick={async () => { const r = await act.run(() => api(`/custom-requests/${req.id}/tailor-decision`, { body: { action: "reject", reason } })); if (r) reload(); }}>Tolak</button>
          </div>
        </Block>
      )}
      {canSpec && (
        <Block title="Spesifikasi produksi dan penawaran">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Kain yang dibeli (m / potong)"><input className="field" inputMode="decimal" value={qty} onChange={(e) => setQty(e.target.value)} /></Field>
            <Field label="Lama pengerjaan (hari)"><input className="field" inputMode="numeric" value={lead} onChange={(e) => setLead(e.target.value)} /></Field>
            {dimKeys.map((k) => <Field key={k} label={`Ukuran jadi: ${k === "chest_width" ? "lebar dada" : "panjang"} (cm)`}><input className="field" inputMode="decimal" value={dims[k] ?? ""} onChange={(e) => setDims({ ...dims, [k]: e.target.value })} /></Field>)}
          </div>
          <Field label="Catatan motif"><input className="field" value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
          <div className="grid gap-2">
            <p className="text-base">Biaya tambahan</p>
            {sur.map((s, i) => (
              <div key={i} className="grid gap-3 sm:grid-cols-[1fr_10rem]">
                <input className="field" placeholder="Deskripsi" aria-label="Deskripsi biaya" value={s.description} onChange={(e) => setSur(sur.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)))} />
                <input className="field" placeholder="Rp" aria-label="Jumlah biaya" inputMode="numeric" value={s.amount} onChange={(e) => setSur(sur.map((x, j) => (j === i ? { ...x, amount: e.target.value.replace(/\D/g, "") } : x)))} />
              </div>
            ))}
            <button type="button" className="btn btn-quiet w-fit" onClick={() => setSur([...sur, { description: "", amount: "" }])}>Tambah biaya</button>
          </div>
          <div className="grid gap-2">
            <p className="text-base">Bahan tambahan</p>
            {mat.map((m, i) => (
              <div key={i} className="grid gap-3 sm:grid-cols-[1fr_9rem_10rem]">
                <input className="field" placeholder="Nama bahan" aria-label="Nama bahan" value={m.name} onChange={(e) => setMat(mat.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} />
                <select className="field" aria-label="Penyedia" value={m.provider} onChange={(e) => setMat(mat.map((x, j) => (j === i ? { ...x, provider: e.target.value as "tailor" | "merchant" } : x)))}><option value="tailor">Penjahit</option><option value="merchant">Penjual</option></select>
                <input className="field" placeholder="Rp" aria-label="Harga bahan" inputMode="numeric" value={m.price} onChange={(e) => setMat(mat.map((x, j) => (j === i ? { ...x, price: e.target.value.replace(/\D/g, "") } : x)))} />
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
            }}>Terbitkan spesifikasi</button>
            {specId && <button className="btn btn-quiet" disabled={act.busy} onClick={() => issue(specId)}>Terbitkan penawaran</button>}
          </div>
        </Block>
      )}
      {quotes.length > 0 && <p className="text-base text-muted">Penawaran terakhir: {idr(quotes[0].total_idr)} ({quotes[0].status}).</p>}
    </>
  );
}

function Detail() {
  const { id } = useParams<{ id: string }>();
  const { has } = useAuth();
  const roles = (["buyer", "merchant", "tailor"] as const).filter((r) => has(r));
  const asParam = useSearchParams().get("as");
  const role = roles.find((r) => r === asParam) ?? roles[0] ?? "buyer";
  const { data: req, error, loading, reload } = useLoad(() => api<Req>(`/custom-requests/${id}`), `${id}-${role}`);
  const quotes = useLoad(() => api<Quote[]>(`/custom-requests/${id}/quotes`).catch(() => [] as Quote[]), `${id}-${req?.status ?? ""}`);
  if (loading) return <p>Memuat…</p>;
  if (error || !req) return <Notice tone="error">{error ?? "Permintaan tidak ditemukan."}</Notice>;
  return (
    <div className="grid gap-12 md:grid-cols-12">
      <div className="grid content-start gap-10 md:col-span-7">
        <div>
          <p className="text-base text-muted">Permintaan baju · revisi {req.revision}</p>
          <h2 className="t-head" style={{ fontSize: "clamp(2rem, 1.3rem + 3.2vw, 3.5rem)" }}>{REQUEST_STATUS[req.status] ?? req.status}</h2>
        </div>
        {role === "buyer" && <Buyer req={req} quotes={quotes.data ?? []} reload={() => { reload(); quotes.reload(); }} />}
        {role === "merchant" && <Merchant req={req} reload={reload} />}
        {role === "tailor" && <Tailor req={req} quotes={quotes.data ?? []} reload={() => { reload(); quotes.reload(); }} />}
      </div>
      <aside className="grid content-start gap-6 md:col-span-4 md:col-start-9">
        {req.design_state && (
          <div className="grid gap-1 bg-surface p-5 text-base">
            <h3 className="mb-1 text-lg font-medium" style={H}>Desain</h3>
            {Object.entries(req.design_state).map(([k, v]) => <p key={k} className="flex justify-between gap-4"><span className="text-muted">{label(OPTION_LABEL, k)}</span><span>{label(VALUE_LABEL, String(v))}</span></p>)}
          </div>
        )}
        {req.measurements_cm && (
          <div className="grid gap-1 bg-surface p-5 text-base">
            <h3 className="mb-1 text-lg font-medium" style={H}>Ukuran (cm)</h3>
            {Object.entries(req.measurements_cm).map(([k, v]) => <p key={k} className="flex justify-between gap-4"><span className="text-muted">{label(DIM_LABEL, k)}</span><span>{v}</span></p>)}
          </div>
        )}
        {req.estimate?.purchase_quantity && <p className="text-base">Estimasi kain: beli {req.estimate.purchase_quantity}, sisa {req.estimate.surplus_m} m.</p>}
        {req.address && role !== "merchant" && <p className="text-base text-muted">Tujuan: {req.address.city}, {req.address.province}</p>}
      </aside>
    </div>
  );
}

export default function RequestPage() {
  return (
    <Page>
      <p className="mb-2 mt-6 text-base"><Link href="/requests" className="link">← Semua permintaan</Link></p>
      <RequireAuth><Suspense fallback={null}><Detail /></Suspense></RequireAuth>
    </Page>
  );
}
