"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { ArrowUpRight, MessageCircle, Truck } from "lucide-react";
import { Field, Notice, RequireAuth, useAction, useLoad } from "@/components/ui";
import { WorkspaceError, WorkspaceLoading, WorkspaceRoute } from "@/components/PartnerWorkspace";
import { api, idr, when } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { actionsFor, statusLabel, type Role } from "@/lib/orderFlow";
import { OrderFinancials } from "@/components/OrderFinancials";
import { OrderAmendments } from "@/components/OrderAmendments";

type Order = {
  id: string; kind: string; status: string; total_idr: number; created_at: string;
  snapshot: {
    listing?: { title: string };
    merchant?: { shop_name: string };
    quantity?: string;
    subtotal_idr?: number;
    shipping_idr?: number;
    address?: { line1: string; city: string };
    quote?: { lines?: { kind: string; description: string; amount_idr: number }[] };
  };
  payment: { status: string; amount_idr: number } | null;
  shipments: { leg: string; status: string; tracking_no: string | null; shipping_idr: number; simulated: boolean }[];
  events: { type: string; to_status: string; note: string | null; simulated: boolean; created_at: string }[];
  simulation_notice: string;
};

const LEG: Record<string, string> = { merchant_to_buyer: "Penjual → pembeli", merchant_to_tailor: "Penjual → penjahit", tailor_to_buyer: "Penjahit → pembeli" };

function Inspection({ orderId, onDone }: { orderId: string; onDone: () => void }) {
  const act = useAction();
  const [passed, setPassed] = useState(true);
  const [width, setWidth] = useState("");
  const [length, setLength] = useState("");
  const [cond, setCond] = useState("baik");
  const [notes, setNotes] = useState("");
  return (
    <form
      className="workspace-detail-card grid gap-4"
      onSubmit={async (e) => {
        e.preventDefault();
        const r = await act.run(() => api(`/orders/${orderId}/fabric-inspection`, { body: { passed, measured_width_cm: width, measured_length_m: length, condition: cond, notes: notes || null } }));
        if (r) onDone();
      }}
    >
      <h2 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Periksa kain yang diterima</h2>
      <Field label="Lebar terukur (cm)"><input className="field" required inputMode="decimal" value={width} onChange={(e) => setWidth(e.target.value)} /></Field>
      <Field label="Panjang terukur (m)"><input className="field" required inputMode="decimal" value={length} onChange={(e) => setLength(e.target.value)} /></Field>
      <Field label="Kondisi"><input className="field" required value={cond} onChange={(e) => setCond(e.target.value)} /></Field>
      <label className="flex items-center gap-3 text-base"><input type="checkbox" checked={passed} onChange={(e) => setPassed(e.target.checked)} className="size-5" /> Kain sesuai pesanan dan layak dijahit</label>
      <Field label={passed ? "Catatan pemeriksaan" : "Jelaskan masalah kain (wajib)"}><textarea className="field" required={!passed} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <button className="btn w-fit" disabled={act.busy}>Simpan hasil pemeriksaan</button>
    </form>
  );
}

function Detail() {
  const { id } = useParams<{ id: string }>();
  const { has } = useAuth();
  const roles = (["buyer", "merchant", "tailor", "admin"] as const).filter((r) => has(r));
  const asParam = useSearchParams().get("as");
  const role = (roles.find((r) => r === asParam) ?? roles[0] ?? "buyer") as Role;
  const { data: o, error, loading, reload } = useLoad(() => api<Order>(`/orders/${id}`), id);
  const act = useAction();
  const [note, setNote] = useState("");

  if (loading) return <WorkspaceLoading>Memuat detail pesanan…</WorkspaceLoading>;
  if (error || !o) return <WorkspaceError message={error ?? "Pesanan tidak ditemukan."} retry={reload} />;
  const snap = o.snapshot;
  const actions = actionsFor(o.kind, o.status, role);
  const needsNote = actions.some((a) => a.needsNote);
  const quote = snap.quote;
  return (
    <div className="workspace-detail grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="workspace-detail-main grid content-start gap-6">
        <div className="workspace-detail-hero">
          <p className="text-base text-muted">{o.kind === "custom" ? "Baju custom" : "Pembelian kain"} · {when(o.created_at)}</p>
          <h2 className="workspace-detail-title t-statement">{statusLabel(o.status)}</h2>
          <p className="text-lg">{snap.listing?.title}{snap.merchant?.shop_name ? ` · ${snap.merchant.shop_name}` : ""}</p>
          <span className="workspace-id">ID pesanan · {o.id}</span>
        </div>

        {act.error && <Notice tone="error">{act.error}</Notice>}
        {actions.length > 0 && (
          <section className="workspace-detail-card grid gap-4"><h2>Langkah berikutnya</h2>
            {needsNote && <Field label={actions.find((a) => a.needsNote)?.event === "cancel" ? "Alasan pembatalan" : actions.find((a) => a.needsNote)?.notePlaceholder ?? "Catatan"} hint={actions.find((a) => a.needsNote)?.event === "cancel" ? "Hanya diperlukan jika Anda membatalkan pesanan." : undefined}><textarea className="field" value={note} onChange={(e) => setNote(e.target.value)} /></Field>}
            <div className="flex flex-wrap gap-3">
              {actions.map((a) => (
                <button key={a.event} className={`btn ${a.event === "cancel" ? "btn-quiet" : ""}`} disabled={act.busy || (a.needsNote && !note.trim())} onClick={async () => { const r = await act.run(() => api(`/orders/${id}/events`, { body: { event: a.event, note: a.needsNote ? note : null } })); if (r) { setNote(""); reload(); } }}>{a.label}</button>
              ))}
            </div>
          </section>
        )}
        {role === "tailor" && o.kind === "custom" && o.status === "received_by_tailor" && <Inspection orderId={id} onDone={reload} />}
        {o.kind === "custom" && <OrderAmendments orderId={id} buyer={role === "buyer"} canPropose={role !== "admin"} />}

        <section className="workspace-detail-card">
          <h2>Perjalanan pesanan</h2>
          <ol className="workspace-timeline grid list-none gap-0 p-0">
            {[...o.events].reverse().map((e, i) => (
              <li key={i} className="grid gap-1">
                <span className="text-lg">{statusLabel(e.to_status)}{e.simulated && <span className="t-small ml-2 bg-surface px-2 py-0.5">simulasi</span>}</span>
                <span className="text-base text-muted">{when(e.created_at)}{e.note ? ` · ${e.note}` : ""}</span>
              </li>
            ))}
          </ol>{o.events.length === 0 && <p className="text-base text-muted">Pembaruan pesanan akan muncul di sini.</p>}
        </section>
      </div>

      <aside className="workspace-detail-aside grid content-start gap-6">
        <section className="workspace-detail-card grid gap-3">
          <h2>Ringkasan pembayaran</h2>
          {quote?.lines ? quote.lines.map((l, i) => <p key={i} className="flex justify-between gap-4 text-base"><span>{l.description}</span><span>{idr(l.amount_idr)}</span></p>) : (<>
            <p className="flex justify-between gap-4 text-base"><span>Kain ({snap.quantity})</span><span>{idr(snap.subtotal_idr ?? 0)}</span></p>
            <p className="flex justify-between gap-4 text-base"><span>Ongkir</span><span>{idr(snap.shipping_idr ?? 0)}</span></p></>)}
          <p className="mt-2 flex justify-between gap-4 border-t border-ink/10 pt-4 text-lg font-semibold"><span>Total</span><span>{idr(o.total_idr)}</span></p>
          <p className="text-base text-muted">Pembayaran: {{ succeeded: "Berhasil", pending: "Menunggu pembayaran", failed: "Gagal", refunded: "Dikembalikan" }[o.payment?.status ?? ""] ?? o.payment?.status ?? "—"}</p>
        </section>
        <section className="workspace-detail-card">
          <h2 className="flex items-center gap-2"><Truck size={17} strokeWidth={1.5} />Pengiriman</h2>
          {o.shipments.map((s) => (
            <div key={s.leg} className="mb-4 grid gap-1 text-base"><strong className="font-medium">{LEG[s.leg] ?? s.leg}</strong><span>{{ pending: "Menunggu pengiriman", shipped: "Dalam pengiriman", delivered: "Sudah tiba", preparing: "Sedang disiapkan" }[s.status] ?? s.status}{s.tracking_no ? ` · ${s.tracking_no}` : ""}</span><span className="block text-muted">{idr(s.shipping_idr)}{s.simulated ? " · simulasi" : ""}</span></div>
          ))}
          {o.shipments.length === 0 && <p className="text-base text-muted">Informasi pengiriman akan tersedia setelah pesanan disiapkan.</p>}
          {snap.address && role === "buyer" && <p className="text-base text-muted">Alamat: {snap.address.line1}, {snap.address.city}</p>}
        </section>
        <div className="workspace-detail-card grid gap-3 text-base">
          <Link href={`/orders/${id}/chat?as=${role}`} className="workspace-link"><MessageCircle size={16} />Percakapan pesanan<ArrowUpRight size={14} /></Link>
          {role === "buyer" && ["delivered", "completed"].includes(o.status) && <Link href={`/orders/${id}/claim`} className="btn btn-quiet w-fit no-underline">Ajukan klaim</Link>}
        </div>
        <OrderFinancials orderId={id} />
        <p className="t-small text-muted">{o.simulation_notice}</p>
      </aside>
    </div>
  );
}

export default function OrderPage() {
  return (
    <Suspense fallback={<WorkspaceLoading />}><RequireAuth><WorkspaceRoute active="orders" title="Detail pesanan" description="Semua informasi dan langkah berikutnya untuk pesanan ini." back={{ href: "/orders", label: "Pesanan" }}><Detail /></WorkspaceRoute></RequireAuth></Suspense>
  );
}
