"use client";

import { useState } from "react";
import { api, idr, when } from "@/lib/api";
import { Field, Notice, useAction, useLoad } from "@/components/ui";

type Amendment = { id: string; reason: string; changes: Record<string, unknown>; price_delta_idr: number; status: string; created_at: string; note: string };

export function OrderAmendments({ orderId, buyer, canPropose }: { orderId: string; buyer: boolean; canPropose: boolean }) {
  const amendments = useLoad(() => api<Amendment[]>(`/orders/${orderId}/amendments`), orderId);
  const act = useAction();
  const [reason, setReason] = useState("");
  const [description, setDescription] = useState("");
  const [delta, setDelta] = useState("0");
  return <section className="workspace-detail-card grid gap-4"><h2 className="text-xl font-semibold">Perubahan pesanan</h2>
    <p className="text-base">Perubahan dicatat terpisah dari pesanan yang disetujui. Selisih harga tidak diproses otomatis.</p>
    {amendments.error && <Notice tone="error">{amendments.error}</Notice>}{act.error && <Notice tone="error">{act.error}</Notice>}
    {amendments.loading && <p className="text-base text-muted" role="status">Memuat perubahan pesanan…</p>}
    {amendments.data?.map((item) => <div key={item.id} className="grid gap-2 rounded-xl bg-surface p-5"><p>{{ proposed: "Menunggu persetujuan", approved: "Disetujui", rejected: "Ditolak" }[item.status] ?? item.status} · {when(item.created_at)}</p><p>{item.reason}</p><dl className="grid gap-1 text-base">{Object.entries(item.changes).map(([key, value]) => <div key={key}><dt className="font-medium">{key === "description" ? "Rincian perubahan" : key}</dt><dd>{typeof value === "string" ? value : JSON.stringify(value)}</dd></div>)}</dl><p>Selisih: {idr(item.price_delta_idr)}</p><p className="text-base">{item.note}</p>
      {buyer && item.status === "proposed" && <div className="flex gap-3">{(["approve", "reject"] as const).map((decision) => <button key={decision} className="btn btn-quiet" disabled={act.busy} onClick={async () => { const result = await act.run(() => api(`/orders/${orderId}/amendments/${item.id}/decision`, { body: { decision } })); if (result) amendments.reload(); }}>{decision === "approve" ? "Setujui" : "Tolak"}</button>)}</div>}
    </div>)}
    {canPropose && <details><summary className="cursor-pointer underline">Ajukan perubahan</summary><div className="mt-4 grid gap-4"><Field label="Alasan perubahan"><textarea className="field" value={reason} onChange={(e) => setReason(e.target.value)} /></Field><Field label="Perubahan yang diusulkan"><textarea className="field" value={description} onChange={(e) => setDescription(e.target.value)} /></Field><Field label="Selisih harga simulasi (Rp)"><input className="field" type="number" value={delta} onChange={(e) => setDelta(e.target.value)} /></Field><button className="btn w-fit" disabled={act.busy || !reason.trim() || !description.trim() || !Number.isFinite(Number(delta))} onClick={async () => { const result = await act.run(() => api(`/orders/${orderId}/amendments`, { body: { reason, changes: { description }, price_delta_idr: Number(delta) } })); if (result) { setReason(""); setDescription(""); setDelta("0"); amendments.reload(); } }}>Ajukan perubahan</button></div></details>}
  </section>;
}
