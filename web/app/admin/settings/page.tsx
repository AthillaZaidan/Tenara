"use client";

import Link from "next/link";
import { useState } from "react";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, when } from "@/lib/api";

type Rule = { id: string; applies_to: string; rate_bps: number; active: boolean; created_at: string };
type Audit = { id: string; action: string; actor_user_id: string | null; target_type: string; target_id: string | null; created_at: string };
type AuditPage = { items: Audit[]; next_cursor: string | null };

function Settings() {
  const rules = useLoad(() => api<Rule[]>("/admin/commission-rules"), "rules");
  const audit = useLoad(() => api<AuditPage>("/admin/audit-events?limit=50"), "audit");
  const action = useAction();
  const [type, setType] = useState("merchant_fabric");
  const [percent, setPercent] = useState("5");
  const [more, setMore] = useState<Audit[]>([]);
  const [next, setNext] = useState<string | null | undefined>();
  const cursor = next === undefined ? audit.data?.next_cursor : next;
  const [synced, setSynced] = useState(false);
  return <div className="grid max-w-4xl gap-12">
    {action.error && <Notice tone="error">{action.error}</Notice>}
    <section className="grid gap-4"><h2 className="t-head text-3xl">Aturan komisi</h2><p className="text-base">Komisi dan settlement pada versi ini adalah simulasi. Perubahan berlaku untuk aturan berikutnya.</p>
      {rules.error && <Notice tone="error">{rules.error}</Notice>}
      <ul className="grid list-none gap-3 p-0">{rules.data?.map((rule) => <li key={rule.id} className="rounded-xl bg-surface p-4">{rule.applies_to === "merchant_fabric" ? "Kain penjual" : "Jasa penjahit"} · {rule.rate_bps / 100}% · {rule.active ? "aktif" : "tidak aktif"} · {when(rule.created_at)}</li>)}</ul>
      <div className="grid gap-4 sm:grid-cols-2"><Field label="Jenis komisi"><select className="field" value={type} onChange={(event) => setType(event.target.value)}><option value="merchant_fabric">Kain penjual</option><option value="tailoring">Jasa penjahit</option></select></Field><Field label="Persentase (0–50%)"><input className="field" type="number" min="0" max="50" step="0.01" value={percent} onChange={(event) => setPercent(event.target.value)} /></Field></div>
      <button className="btn w-fit" disabled={action.busy || !percent || Number(percent) < 0 || Number(percent) > 50} onClick={async () => { const result = await action.run(() => api("/admin/commission-rules", { body: { applies_to: type, rate_bps: Math.round(Number(percent) * 100) } })); if (result) rules.reload(); }}>Simpan aturan</button>
    </section>
    <section className="grid gap-4"><h2 className="t-head text-3xl">Pola baju</h2><p className="text-base">Sinkronkan definisi pola platform dengan konfigurasi backend.</p><button className="btn btn-quiet w-fit" disabled={action.busy} onClick={async () => { const result = await action.run(() => api("/admin/garment-templates/sync", { method: "POST" })); if (result) setSynced(true); }}>Sinkronkan pola</button>{synced && <Notice>Pola telah disinkronkan.</Notice>}</section>
    <section className="grid gap-4"><h2 className="t-head text-3xl">Aktivitas audit</h2>{audit.error && <Notice tone="error">{audit.error}</Notice>}<ul className="grid list-none gap-3 p-0">{[...(audit.data?.items ?? []), ...more].map((event) => <li key={event.id} className="rounded-xl bg-surface p-4 text-base"><strong>{event.action}</strong><p>{event.target_type} · {event.target_id ?? "-"}</p><p className="text-muted">{when(event.created_at)} · {event.actor_user_id ?? "sistem"}</p></li>)}</ul>
      {cursor && <button className="btn btn-quiet w-fit" disabled={action.busy} onClick={async () => { const page = await action.run(() => api<AuditPage>(`/admin/audit-events?limit=50&cursor=${encodeURIComponent(cursor)}`)); if (page) { setMore((items) => [...items, ...page.items]); setNext(page.next_cursor); } }}>Muat lebih banyak</button>}
    </section>
  </div>;
}

export default function AdminSettingsPage() { return <Page><p className="mb-4 mt-6"><Link href="/admin" className="link">← Admin</Link></p><h1 className="t-head mb-10">Pengaturan dan audit</h1><RequireAuth role="admin"><Settings /></RequireAuth></Page>; }
