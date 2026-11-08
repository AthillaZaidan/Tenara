"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, idr, newKey, when } from "@/lib/api";

type Checkout = {
  id: string; status: string; listing_title: string; quantity: number; selling_unit: string; unit_price_idr: number;
  subtotal_idr: number; shipping_idr: number; service_fee_idr: number; total_idr: number; expires_at: string | null;
  address: { recipient_name: string; line1: string; city: string; province: string };
  payment: { id: string; status: string } | null; simulation_notice: string;
};

function useCountdown(iso: string | null) {
  const [left, setLeft] = useState<number | null>(null);
  useEffect(() => {
    if (!iso) return;
    const tick = () => setLeft(Math.max(0, Math.floor((new Date(iso).getTime() - Date.now()) / 1000)));
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [iso]);
  return left;
}

function CheckoutView() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: co, error, reload, loading } = useLoad(() => api<Checkout>(`/fabric-checkouts/${id}`), id);
  const act = useAction();
  const left = useCountdown(co?.expires_at ?? null);

  if (loading) return <p className="py-16">Memuat…</p>;
  if (error || !co) return <Notice tone="error">{error ?? "Checkout tidak ditemukan."}</Notice>;
  const expired = left === 0 || co.status === "expired";
  const rows: [string, number][] = [
    [`${co.listing_title} (${co.quantity} ${co.selling_unit === "meter" ? "m" : "potong"} × ${idr(co.unit_price_idr)})`, co.subtotal_idr],
    ["Ongkos kirim (simulasi)", co.shipping_idr],
    ...(co.service_fee_idr ? ([["Biaya layanan", co.service_fee_idr]] as [string, number][]) : []),
  ];
  return (
    <div className="grid max-w-2xl gap-8">
      <Notice>{co.simulation_notice}</Notice>
      <dl className="grid gap-3">
        {rows.map(([k, v]) => (<div key={k} className="flex justify-between gap-6"><dt>{k}</dt><dd>{idr(v)}</dd></div>))}
        <div className="flex justify-between gap-6 bg-surface p-4 text-xl"><dt>Total</dt><dd>{idr(co.total_idr)}</dd></div>
      </dl>
      <p className="text-base">Dikirim ke {co.address.recipient_name}, {co.address.line1}, {co.address.city}, {co.address.province}.</p>

      {co.status === "review" && (
        <>
          <p className="text-base">Menekan tombol di bawah menahan stok selama 15 menit sampai pembayaran selesai.</p>
          {act.error && <Notice tone="error">{act.error}</Notice>}
          <button className="btn w-fit" disabled={act.busy} onClick={async () => { const r = await act.run(() => api(`/fabric-checkouts/${id}/confirm`, { body: { expected_total_idr: co.total_idr }, idempotencyKey: newKey() })); if (r) reload(); }}>Tahan stok dan bayar</button>
        </>
      )}
      {co.status === "payment_pending" && co.payment && (
        <>
          <p>{expired ? "Waktu pembayaran habis; stok dilepas." : <>Stok ditahan sampai {when(co.expires_at)} (sisa {Math.floor((left ?? 0) / 60)}:{String((left ?? 0) % 60).padStart(2, "0")}).</>}</p>
          {act.error && <Notice tone="error">{act.error}</Notice>}
          <div className="flex flex-wrap gap-4">
            <button className="btn" disabled={act.busy || expired} onClick={async () => { const r = await act.run(() => api<{ order: { id: string } }>(`/demo-payments/${co.payment!.id}/complete`, { body: { outcome: "succeeded" }, idempotencyKey: newKey() })); if (r) router.push(`/orders/${r.order.id}`); }}>Bayar (simulasi berhasil)</button>
            <button className="btn btn-quiet" disabled={act.busy || expired} onClick={async () => { const r = await act.run(() => api(`/demo-payments/${co.payment!.id}/complete`, { body: { outcome: "failed" }, idempotencyKey: newKey() })); if (r) reload(); }}>Simulasikan gagal</button>
          </div>
        </>
      )}
      {["expired", "failed", "cancelled"].includes(co.status) && (
        <>
          <Notice tone="error">Checkout ini {co.status === "expired" ? "kedaluwarsa" : "tidak berhasil"}.</Notice>
          <Link href="/gallery" className="btn w-fit no-underline">Kembali ke Gallery</Link>
        </>
      )}
    </div>
  );
}

export default function CheckoutPage() {
  return (
    <Page>
      <h1 className="t-head mb-10 mt-8">Pembayaran</h1>
      <RequireAuth><CheckoutView /></RequireAuth>
    </Page>
  );
}
