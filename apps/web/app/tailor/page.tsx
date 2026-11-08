"use client";

import Link from "next/link";
import { useState } from "react";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, idr } from "@/lib/api";

type Cap = { template_code: string; base_rate_idr: number; lead_time_days: number; weekly_capacity: number; materials: string[] };
type Tpl = { code: string; name: string };

function Row({ tpl, cap, reload }: { tpl: Tpl; cap?: Cap; reload: () => void }) {
  const act = useAction();
  const [rate, setRate] = useState(String(cap?.base_rate_idr ?? ""));
  const [lead, setLead] = useState(String(cap?.lead_time_days ?? "14"));
  const [week, setWeek] = useState(String(cap?.weekly_capacity ?? "3"));
  const [mats, setMats] = useState((cap?.materials ?? ["katun", "tenun"]).join(", "));
  return (
    <li className="grid gap-4 bg-surface p-5">
      <h3 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>{tpl.name} <span className="text-base text-muted">({tpl.code}){cap ? ` · mulai ${idr(cap.base_rate_idr)}` : " · belum ditawarkan"}</span></h3>
      <div className="grid gap-3 sm:grid-cols-4">
        <Field label="Tarif dasar (Rp)"><input className="field" inputMode="numeric" value={rate} onChange={(e) => setRate(e.target.value.replace(/\D/g, ""))} /></Field>
        <Field label="Lama (hari)"><input className="field" inputMode="numeric" value={lead} onChange={(e) => setLead(e.target.value)} /></Field>
        <Field label="Kapasitas / minggu"><input className="field" inputMode="numeric" value={week} onChange={(e) => setWeek(e.target.value)} /></Field>
        <Field label="Bahan (pisahkan koma)"><input className="field" value={mats} onChange={(e) => setMats(e.target.value)} /></Field>
      </div>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <div className="flex gap-3">
        <button className="btn w-fit" disabled={act.busy || !rate} onClick={async () => { const r = await act.run(() => api(`/tailor/capabilities/${tpl.code}`, { method: "PUT", body: { base_rate_idr: Number(rate), lead_time_days: Number(lead) || 1, weekly_capacity: Number(week) || 1, materials: mats.split(",").map((m) => m.trim()).filter(Boolean), supported_options: {} } })); if (r) reload(); }}>{cap ? "Perbarui" : "Tawarkan"}</button>
        {cap && <button className="btn btn-quiet w-fit" disabled={act.busy} onClick={async () => { const r = await act.run(() => api(`/tailor/capabilities/${tpl.code}`, { method: "DELETE" })); if (r !== undefined) reload(); }}>Hentikan</button>}
      </div>
    </li>
  );
}

function Dashboard() {
  const caps = useLoad(() => api<Cap[]>("/tailor/capabilities"), "caps");
  const tpls = useLoad(() => api<Tpl[]>("/garment-templates"), "tpls");
  return (
    <div className="grid gap-10">
      <div className="flex flex-wrap gap-3">
        <Link href="/requests?as=tailor" className="btn no-underline">Permintaan baju</Link>
        <Link href="/orders?as=tailor" className="btn btn-quiet no-underline">Pesanan</Link>
      </div>
      <p className="max-w-[60ch]">Atur pola pakaian yang Anda terima. Tarif dan lama pengerjaan yang Anda deklarasikan dipakai untuk merekomendasikan Anda ke pembeli, dan Anda tetap memvalidasi tiap desain.</p>
      {caps.error && <Notice tone="error">{caps.error}</Notice>}
      <ul className="grid max-w-4xl list-none gap-5 p-0">
        {tpls.data?.map((t) => <Row key={t.code + (caps.data?.find((c) => c.template_code === t.code)?.base_rate_idr ?? "")} tpl={t} cap={caps.data?.find((c) => c.template_code === t.code)} reload={caps.reload} />)}
      </ul>
    </div>
  );
}

export default function TailorPage() {
  return (
    <Page>
      <h1 className="t-head mb-10 mt-8">Dasbor penjahit</h1>
      <RequireAuth role="tailor"><Dashboard /></RequireAuth>
    </Page>
  );
}
