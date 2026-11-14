"use client";

import { api, idr } from "@/lib/api";
import { Notice, useLoad } from "@/components/ui";

type Settlement = { simulation_notice: string; entries?: { party_role: string; kind: string; gross_idr: number; commission_bps: number; commission_idr: number; net_idr: number; note: string | null }[] };

export function OrderFinancials({ orderId }: { orderId: string }) {
  const settlement = useLoad(() => api<Settlement>(`/orders/${orderId}/settlement`), orderId);
  return <details className="workspace-collapse grid rounded-xl bg-surface p-5"><summary className="cursor-pointer font-medium">Rincian pendapatan & komisi</summary>
    {settlement.loading && <p className="mt-4 text-base text-muted" role="status">Memuat rincian pendapatan…</p>}
    {settlement.error && <Notice tone="error">{settlement.error}</Notice>}
    <p className="mt-4 text-base">{settlement.data?.simulation_notice}</p>
    {settlement.data?.entries?.map((item, index) => <div key={index} className="mt-4 grid gap-3 border-t border-current/10 pt-4 text-base"><p className="font-medium">{{ merchant: "Penjual", tailor: "Penjahit", platform: "Tenara" }[item.party_role] ?? item.party_role} · {{ fabric: "Kain", tailoring: "Jasa jahit", shipping: "Pengiriman" }[item.kind] ?? item.kind}</p><dl className="workspace-key-values"><div><dt>Pendapatan</dt><dd>{idr(item.gross_idr)}</dd></div><div><dt>Komisi ({item.commission_bps / 100}%)</dt><dd>{idr(item.commission_idr)}</dd></div><div className="workspace-total"><dt>Pendapatan bersih</dt><dd>{idr(item.net_idr)}</dd></div></dl>{item.note && <p className="text-muted">{item.note}</p>}</div>)}
    {settlement.data && !settlement.data.entries?.length && <p className="mt-3 text-base">Rincian pembeli tersedia pada ringkasan pesanan.</p>}
  </details>;
}
