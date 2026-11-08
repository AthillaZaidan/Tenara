"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, idr, when } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { actionsFor, statusLabel, type Role } from "@/lib/orderFlow";

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
  return (
    <form
      className="grid max-w-xl gap-4 bg-surface p-6"
      onSubmit={async (e) => {
        e.preventDefault();
        const r = await act.run(() => api(`/orders/${orderId}/fabric-inspection`, { body: { passed, measured_width_cm: width, measured_length_m: length, condition: cond } }));
        if (r) onDone();
      }}
    >
      <h2 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Periksa kain yang diterima</h2>
      <Field label="Lebar terukur (cm)"><input className="field" required inputMode="decimal" value={width} onChange={(e) => setWidth(e.target.value)} /></Field>
      <Field label="Panjang terukur (m)"><input className="field" required inputMode="decimal" value={length} onChange={(e) => setLength(e.target.value)} /></Field>
      <Field label="Kondisi"><input className="field" required value={cond} onChange={(e) => setCond(e.target.value)} /></Field>
      <label className="flex items-center gap-3 text-base"><input type="checkbox" checked={passed} onChange={(e) => setPassed(e.target.checked)} className="size-5" /> Kain sesuai pesanan dan layak dijahit</label>
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

  if (loading) return <p>Memuat…</p>;
  if (error || !o) return <Notice tone="error">{error ?? "Pesanan tidak ditemukan."}</Notice>;
  const snap = o.snapshot;
  const actions = actionsFor(o.kind, o.status, role);
  const needsNote = actions.some((a) => a.needsNote);
  const quote = snap.quote;
  return (
    <div className="grid gap-12 md:grid-cols-12">
      <div className="grid content-start gap-10 md:col-span-7">
        <div>
          <p className="text-base text-muted">{o.kind === "custom" ? "Baju custom" : "Pembelian kain"} · {when(o.created_at)}</p>
          <h2 className="t-head" style={{ fontSize: "clamp(2rem, 1.3rem + 3.2vw, 3.5rem)" }}>{statusLabel(o.status)}</h2>
          <p className="mt-2 text-lg">{snap.listing?.title}{snap.merchant?.shop_name ? ` · ${snap.merchant.shop_name}` : ""}</p>
        </div>

        {act.error && <Notice tone="error">{act.error}</Notice>}
        {actions.length > 0 && (
          <div className="grid gap-4">
            {needsNote && <Field label={actions.find((a) => a.needsNote)?.notePlaceholder ?? "Catatan"}><textarea className="field" value={note} onChange={(e) => setNote(e.target.value)} /></Field>}
            <div className="flex flex-wrap gap-3">
              {actions.map((a) => (
                <button key={a.event} className="btn" disabled={act.busy || (a.needsNote && !note.trim())} onClick={async () => { const r = await act.run(() => api(`/orders/${id}/events`, { body: { event: a.event, note: a.needsNote ? note : null } })); if (r) { setNote(""); reload(); } }}>{a.label}</button>
              ))}
            </div>
          </div>
        )}
        {role === "tailor" && o.kind === "custom" && o.status === "received_by_tailor" && <Inspection orderId={id} onDone={reload} />}

        <div>
          <h3 className="mb-4 text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Perjalanan pesanan</h3>
          <ol className="grid list-none gap-4 p-0">
            {[...o.events].reverse().map((e, i) => (
              <li key={i} className="grid gap-1">
                <span className="text-lg">{statusLabel(e.to_status)}{e.simulated && <span className="t-small ml-2 bg-surface px-2 py-0.5">simulasi</span>}</span>
                <span className="text-base text-muted">{when(e.created_at)}{e.note ? ` · ${e.note}` : ""}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <aside className="grid content-start gap-8 md:col-span-4 md:col-start-9">
        <div className="grid gap-2 bg-surface p-6">
          <h3 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Ringkasan</h3>
          {quote?.lines ? quote.lines.map((l, i) => <p key={i} className="flex justify-between gap-4 text-base"><span>{l.description}</span><span>{idr(l.amount_idr)}</span></p>) : (<>
            <p className="flex justify-between gap-4 text-base"><span>Kain ({snap.quantity})</span><span>{idr(snap.subtotal_idr ?? 0)}</span></p>
            <p className="flex justify-between gap-4 text-base"><span>Ongkir</span><span>{idr(snap.shipping_idr ?? 0)}</span></p></>)}
          <p className="mt-2 flex justify-between gap-4 text-lg"><span>Total</span><span>{idr(o.total_idr)}</span></p>
          <p className="text-base text-muted">Pembayaran: {o.payment?.status ?? "-"}</p>
        </div>
        <div>
          <h3 className="mb-3 text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Pengiriman</h3>
          {o.shipments.map((s) => (
            <p key={s.leg} className="mb-3 text-base">{LEG[s.leg] ?? s.leg}: {s.status}{s.tracking_no ? ` · ${s.tracking_no}` : ""}<span className="block text-muted">{idr(s.shipping_idr)}{s.simulated ? " · simulasi" : ""}</span></p>
          ))}
          {snap.address && role === "buyer" && <p className="text-base text-muted">Alamat: {snap.address.line1}, {snap.address.city}</p>}
        </div>
        <div className="grid gap-3 text-base">
          <Link href={`/orders/${id}/chat?as=${role}`} className="btn btn-quiet w-fit no-underline">Pesan untuk pesanan ini</Link>
          {role === "buyer" && ["delivered", "completed"].includes(o.status) && <Link href={`/orders/${id}/claim`} className="btn btn-quiet w-fit no-underline">Ajukan klaim</Link>}
        </div>
        <p className="t-small text-muted">{o.simulation_notice}</p>
      </aside>
    </div>
  );
}

export default function OrderPage() {
  return (
    <Page>
      <p className="mb-2 mt-6 text-base"><Link href="/orders" className="link">← Semua pesanan</Link></p>
      <RequireAuth><Suspense fallback={null}><Detail /></Suspense></RequireAuth>
    </Page>
  );
}
