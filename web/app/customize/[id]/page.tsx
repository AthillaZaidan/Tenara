"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AvatarViewer } from "@/components/AvatarViewer";
import { PhotoMeasure } from "@/components/PhotoMeasure";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, fileUrl, idr } from "@/lib/api";
import { DIM_LABEL, OPTION_LABEL, VALUE_LABEL, label, type OptionDef } from "@/lib/design";

type Customization = {
  id: string; listing_id: string; template: { code: string; name: string; required_dimensions: string[] };
  current_revision: number; state: Record<string, string | number>;
  open_clarifications: { id: string; field: string; question: string; choices: string[] }[];
  measurement_set: { id: string; status: string; revision: number } | null;
  material_estimate: { id: string; stale: boolean } | null; ready_for_tailor_validation: boolean;
};
type Proposal = {
  proposal_id: string;
  changes: { field: string; value: string | number; from: string | number; status: string }[];
  unsupported_requests: { text: string; reason: string }[];
  clarifications: { id: string; field: string; text: string; question: string; choices: string[]; direction: number }[];
  fallback: string | null;
};
type Estimate = {
  id: string; stale: boolean; stale_reasons: string[]; notice: string;
  result: { fits: boolean; required_length_cm: number; breakdown_cm: Record<string, number>; assumptions: string[]; selling_unit: string; purchase_quantity: string; surplus_m: string; stock_ok: boolean };
};
type Preview = { id: string; status: string; url: string | null; warnings: string[]; label: string; method: string | null };
type Tailor = { tailor_id: string; shop_name: string; city: string; province: string; experience_years: number; base_rate_idr: number; lead_time_days: number; reasons: string[] };
type Address = { id: string; label: string; recipient_name: string; line1: string; city: string };
type MSet = { id: string; height_cm: number | null; status: string; revision: number; values: { key: string; value_cm: number | null; source: string }[] };

const H = { fontFamily: "var(--font-hanken)" } as const;
const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="grid gap-5"><h2 className="t-head" style={{ fontSize: "clamp(1.75rem, 1.4rem + 1.4vw, 2.5rem)" }}>{title}</h2>{children}</section>
);

function DesignOptions({ cust, onChanged }: { cust: Customization; onChanged: () => void }) {
  const tpl = useLoad(() => api<{ options: Record<string, OptionDef> }>(`/garment-templates/${cust.template.code}`), cust.template.code);
  const act = useAction();
  const [draft, setDraft] = useState<Record<string, string | number>>({});
  const options = tpl.data?.options ?? {};
  const changed = Object.fromEntries(Object.entries(draft).filter(([k, v]) => String(v) !== String(cust.state[k])));
  return (
    <div className="grid gap-5">
      <div className="grid gap-4 sm:grid-cols-2">
        {Object.entries(options).map(([key, def]) => {
          const value = draft[key] ?? cust.state[key] ?? def.default;
          return (
            <Field key={key} label={label(OPTION_LABEL, key)} hint={def.type === "number" ? `${def.min} sampai ${def.max} ${def.unit ?? ""}` : undefined}>
              {def.type === "enum" ? (
                <select className="field" value={String(value)} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}>
                  {def.values.map((v) => <option key={v} value={v}>{label(VALUE_LABEL, v)}</option>)}
                </select>
              ) : (
                <input className="field" type="number" min={def.min} max={def.max} step="0.5" value={String(value)} onChange={(e) => setDraft({ ...draft, [key]: Number(e.target.value) })} />
              )}
            </Field>
          );
        })}
      </div>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <button className="btn w-fit" disabled={act.busy || Object.keys(changed).length === 0}
        onClick={async () => { const r = await act.run(() => api(`/customizations/${cust.id}/revisions`, { body: { expected_design_revision: cust.current_revision, changes: changed } })); if (r) { setDraft({}); onChanged(); } }}>
        Simpan perubahan desain
      </button>
    </div>
  );
}

function PromptBox({ cust, onChanged }: { cust: Customization; onChanged: () => void }) {
  const act = useAction();
  const [prompt, setPrompt] = useState("");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [picks, setPicks] = useState<Record<string, string>>({});
  return (
    <div className="grid gap-4">
      <Field label="Ceritakan perubahan dengan kalimat biasa" hint="Contoh: tambah saku dada kiri, kancing kayu, pendekkan hem 3 cm. Sistem hanya menerapkan opsi yang didukung pola ini.">
        <textarea className="field" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
      </Field>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <button className="btn btn-quiet w-fit" disabled={act.busy || !prompt.trim()}
        onClick={async () => { const p = await act.run(() => api<Proposal>(`/customizations/${cust.id}/prompt-changes`, { body: { expected_design_revision: cust.current_revision, prompt } })); if (p) { setProposal(p); setPicks({}); } }}>
        Tafsirkan permintaan
      </button>
      {proposal && (
        <div className="grid gap-4 bg-surface p-5">
          <h3 className="text-xl font-medium" style={H}>Usulan perubahan</h3>
          {proposal.fallback && <p className="text-base">{proposal.fallback}</p>}
          {proposal.changes.length > 0 ? (
            <ul className="grid list-disc gap-1 pl-5">{proposal.changes.map((c) => <li key={c.field}>{label(OPTION_LABEL, c.field)}: {label(VALUE_LABEL, String(c.from))} → {label(VALUE_LABEL, String(c.value))}</li>)}</ul>
          ) : <p className="text-base">Belum ada perubahan yang bisa diterapkan.</p>}
          {proposal.clarifications.map((c) => (
            <Field key={c.id} label={`${c.question} (“${c.text}”)`}>
              <select className="field" value={picks[c.id] ?? ""} onChange={(e) => setPicks({ ...picks, [c.id]: e.target.value })}>
                <option value="">Pilih…</option>
                {c.choices.map((v) => <option key={v} value={v}>{label(OPTION_LABEL, v)}</option>)}
              </select>
            </Field>
          ))}
          {proposal.unsupported_requests.length > 0 && (
            <div className="text-base"><p className="font-medium">Belum didukung pola ini:</p><ul className="list-disc pl-5">{proposal.unsupported_requests.map((u) => <li key={u.text}>“{u.text}”: {u.reason}</li>)}</ul></div>
          )}
          <p className="text-base text-muted">Penjahit tetap memvalidasi desain sebelum membuat penawaran.</p>
          <button className="btn w-fit" disabled={act.busy || (proposal.changes.length === 0 && Object.keys(picks).length === 0)}
            onClick={async () => { const r = await act.run(() => api(`/customizations/${cust.id}/revisions`, { body: { expected_design_revision: cust.current_revision, proposal_id: proposal.proposal_id, resolutions: picks } })); if (r) { setProposal(null); setPrompt(""); onChanged(); } }}>
            Terapkan ke desain
          </button>
        </div>
      )}
    </div>
  );
}

function Measurements({ cust, onChanged }: { cust: Customization; onChanged: () => void }) {
  const act = useAction();
  const existing = useLoad(() => (cust.measurement_set ? api<MSet>(`/measurement-sets/${cust.measurement_set.id}`) : Promise.resolve(null)), cust.measurement_set?.id ?? "none");
  const [height, setHeight] = useState("");
  const [vals, setVals] = useState<Record<string, string>>({});
  const set = existing.data;
  const current = (k: string) => vals[k] ?? String(set?.values.find((v) => v.key === k)?.value_cm ?? "");
  const body = () => ({ height_cm: height ? Number(height) : set?.height_cm ?? null, values: Object.fromEntries(cust.template.required_dimensions.map((k) => [k, current(k) === "" ? null : Number(current(k))])) });
  const save = async () => {
    const s = set
      ? await act.run(() => api<MSet>(`/measurement-sets/${set.id}`, { method: "PATCH", body: { expected_revision: set.revision, ...body() } }))
      : await act.run(async () => { const m = await api<MSet>("/measurement-sets", { body: body() }); await api(`/customizations/${cust.id}/measurement-set`, { body: { measurement_set_id: m.id } }); return m; });
    if (s) { existing.reload(); onChanged(); }
  };
  return (
    <div className="grid gap-5">
      <PhotoMeasure custId={cust.id} onMeasured={() => { existing.reload(); onChanged(); }} />
      <p className="text-base">Ukur dengan meteran dan isi dalam sentimeter, atau koreksi hasil dari foto. Ukuran Anda hanya dibagikan ke penjahit yang Anda pilih.</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Tinggi badan (cm)"><input className="field" inputMode="decimal" value={height || String(set?.height_cm ?? "")} onChange={(e) => setHeight(e.target.value)} /></Field>
        {cust.template.required_dimensions.map((k) => (
          <Field key={k} label={`${label(DIM_LABEL, k)} (cm)`}><input className="field" inputMode="decimal" value={current(k)} onChange={(e) => setVals({ ...vals, [k]: e.target.value })} /></Field>
        ))}
      </div>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <div className="flex flex-wrap items-center gap-3">
        <button className="btn" disabled={act.busy} onClick={save}>Simpan ukuran</button>
        {set && set.status !== "confirmed" && (
          <button className="btn btn-quiet" disabled={act.busy} onClick={async () => { const r = await act.run(() => api(`/measurement-sets/${set.id}/confirm`, { body: { customization_id: cust.id } })); if (r) { existing.reload(); onChanged(); } }}>Konfirmasi ukuran</button>
        )}
        {set && <span className="text-base">Status: {set.status === "confirmed" ? "dikonfirmasi" : "draf, belum dikonfirmasi"}</span>}
      </div>
    </div>
  );
}

function EstimateBox({ cust, onChanged }: { cust: Customization; onChanged: () => void }) {
  const act = useAction();
  const cur = useLoad(() => (cust.material_estimate ? api<Estimate>(`/customizations/${cust.id}/material-estimates/current`) : Promise.resolve(null)), `${cust.material_estimate?.id ?? "none"}-${cust.current_revision}`);
  const e = cur.data;
  return (
    <div className="grid gap-4">
      <button className="btn w-fit" disabled={act.busy || !cust.measurement_set || cust.measurement_set.status !== "confirmed"}
        onClick={async () => { const r = await act.run(() => api(`/customizations/${cust.id}/material-estimates`, { method: "POST" })); if (r) { cur.reload(); onChanged(); } }}>
        {e ? "Hitung ulang kebutuhan kain" : "Hitung kebutuhan kain"}
      </button>
      {(!cust.measurement_set || cust.measurement_set.status !== "confirmed") && <p className="text-base text-muted">Konfirmasi ukuran dulu.</p>}
      {act.error && <Notice tone="error">{act.error}</Notice>}
      {e && (
        <div className="grid gap-2 bg-surface p-5">
          {e.stale && <Notice tone="error">Estimasi ini sudah usang: {e.stale_reasons.join("; ") || "desain atau ukuran berubah"}. Hitung ulang.</Notice>}
          <p className="text-xl">Perlu sekitar {(e.result.required_length_cm / 100).toFixed(2)} m, beli {e.result.purchase_quantity} {e.result.selling_unit === "meter" ? "m" : "potong"}</p>
          <p className="text-base">Badan {e.result.breakdown_cm.body} cm, lengan {e.result.breakdown_cm.sleeves} cm, opsi {e.result.breakdown_cm.options} cm. Sisa {e.result.surplus_m} m. {e.result.fits && e.result.stock_ok ? "Stok penjual cukup." : "Stok atau ukuran kain belum mencukupi."}</p>
          <ul className="list-disc pl-5 text-base text-muted">{e.result.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
          <p className="text-base">{e.notice}</p>
        </div>
      )}
    </div>
  );
}

/** A preview job: polled until the worker has finished it. */
function usePreview() {
  const [preview, setPreview] = useState<Preview | null>(null);
  const pending = !!preview && ["queued", "processing"].includes(preview.status);
  useEffect(() => {
    if (!preview || !pending) return;
    const t = setInterval(async () => { try { setPreview(await api<Preview>(`/previews/${preview.id}`)); } catch { /* retry on next tick */ } }, 2500);
    return () => clearInterval(t);
  }, [preview, pending]);
  return { preview, setPreview, pending };
}

function PreviewBox({ cust }: { cust: Customization }) {
  const act = useAction();
  const { preview, setPreview, pending } = usePreview();
  return (
    <div className="grid gap-4">
      <button className="btn btn-quiet w-fit" disabled={act.busy || !!pending} onClick={async () => { const p = await act.run(() => api<Preview>(`/customizations/${cust.id}/product-previews`, { method: "POST" })); if (p) setPreview(p); }}>Buat ilustrasi desain</button>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      {pending && <p role="status">Ilustrasi sedang dibuat…</p>}
      {preview?.status === "failed" && <Notice tone="error">Ilustrasi gagal dibuat.</Notice>}
      {preview?.url && <figure className="m-0 grid max-w-md gap-2"><img src={fileUrl(preview.url)} alt="Ilustrasi konseptual desain" className="w-full bg-surface" /><figcaption className="text-base text-muted">{preview.label}</figcaption></figure>}
      {preview?.warnings.map((w) => <p key={w} className="text-base text-muted">{w}</p>)}
    </div>
  );
}

const GENDERS = [["neutral", "Netral"], ["female", "Perempuan"], ["male", "Laki-laki"]] as const;

function AvatarBox({ cust }: { cust: Customization }) {
  const act = useAction();
  const { preview, setPreview, pending } = usePreview();
  const [gender, setGender] = useState("neutral");
  const mset = cust.measurement_set;
  const make = async () => {
    if (!mset) return;
    const p = await act.run(() => api<Preview>(`/customizations/${cust.id}/avatar-previews`, { body: { measurement_set_id: mset.id, gender } }));
    if (p) setPreview(p);
  };
  // warnings start with a machine code ("avatar_mismatch:back_length: ..."); show the sentence after it
  const notes = preview?.warnings.map((w) => w.replace(/^[a-z_]+(:[a-z_]+)?: /, "")) ?? [];
  return (
    <div className="grid gap-4">
      <p className="text-base">Lihat baju ini dipakai badan 3D yang dibentuk dari ukuranmu: tinggi, lingkar, dan panjang yang kamu isi. Avatar dibuat dari angka saja, tanpa foto, dan hanya bisa dilihat olehmu; penjahit tidak menerimanya.</p>
      {!mset && <p className="text-base text-muted">Isi dan simpan ukuran badan (termasuk tinggi) dulu.</p>}
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Bentuk dasar badan">
          <select className="field" value={gender} onChange={(e) => setGender(e.target.value)}>
            {GENDERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
        <button className="btn btn-quiet w-fit" disabled={act.busy || pending || !mset} onClick={make}>{preview?.url ? "Buat ulang avatar 3D" : "Buat avatar 3D"}</button>
      </div>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      {pending && <p role="status">Avatar sedang dibentuk dari ukuranmu…</p>}
      {preview?.status === "failed" && <Notice tone="error">Avatar gagal dibuat.</Notice>}
      {preview?.status === "stale" && <Notice tone="error">Desain atau ukuran sudah berubah sejak avatar ini dibuat. Buat ulang.</Notice>}
      {preview?.url && (
        <figure className="m-0 grid gap-2">
          <AvatarViewer src={fileUrl(preview.url)} alt="Avatar 3D dari ukuranmu memakai baju rancangan" />
          <figcaption className="text-base text-muted">{preview.label} Seret untuk memutar, cubit atau gulir untuk memperbesar.</figcaption>
        </figure>
      )}
      {notes.map((w) => <p key={w} className="text-base text-muted">{w}</p>)}
    </div>
  );
}

function Tailors({ cust }: { cust: Customization }) {
  const router = useRouter();
  const act = useAction();
  const addresses = useLoad(() => api<Address[]>("/addresses"), "addr");
  const [addrId, setAddrId] = useState("");
  const chosen = addrId || addresses.data?.[0]?.id || "";
  const recs = useLoad(() => (chosen ? api<{ items: Tailor[]; notice: string }>(`/tailors/recommendations?customization_id=${cust.id}&delivery_address_id=${chosen}`) : Promise.resolve(null)), `${chosen}-${cust.current_revision}`);
  const choose = async (t: Tailor) => {
    const req = await act.run(async () => {
      const r = await api<{ id: string }>("/custom-requests", { body: { customization_id: cust.id, tailor_id: t.tailor_id, delivery_address_id: chosen } });
      await api(`/custom-requests/${r.id}/submit`, { method: "POST" });
      return r;
    });
    if (req) router.push(`/requests/${req.id}`);
  };
  return (
    <div className="grid gap-5">
      {!cust.ready_for_tailor_validation && <p className="text-base">Lengkapi ukuran dan estimasi kain dulu supaya desain siap divalidasi penjahit.</p>}
      <p className="text-base text-muted">Penjahit yang kamu pilih menerima desain, ilustrasi produk terbaru, ukuran (cm), kebutuhan kain, dan alamat pengiriman. Foto badan dan ilustrasi di fotomu tidak dikirim. Penjual kain hanya menerima jumlah kain.</p>
      <Field label="Alamat pengiriman baju">
        <select className="field" value={chosen} onChange={(e) => setAddrId(e.target.value)}>
          {addresses.data?.map((a) => <option key={a.id} value={a.id}>{a.label}: {a.recipient_name}, {a.line1}, {a.city}</option>)}
        </select>
      </Field>
      {recs.error && <Notice tone="error">{recs.error}</Notice>}
      {act.error && <Notice tone="error">{act.error}</Notice>}
      {recs.data && (
        <>
          <p className="text-base text-muted">{recs.data.notice}</p>
          <ul className="grid list-none gap-6 p-0">
            {recs.data.items.length === 0 && <li>Belum ada penjahit yang cocok untuk desain dan kain ini.</li>}
            {recs.data.items.map((t) => (
              <li key={t.tailor_id} className="grid gap-2 bg-surface p-5">
                <h3 className="text-xl font-medium" style={H}>{t.shop_name}</h3>
                <p className="text-base">{t.city}, {t.province} · {t.experience_years} tahun · mulai {idr(t.base_rate_idr)} · {t.lead_time_days} hari</p>
                <ul className="list-disc pl-5 text-base text-muted">{t.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                <button className="btn mt-2 w-fit" disabled={act.busy || !cust.ready_for_tailor_validation} onClick={() => choose(t)}>Ajukan ke penjahit ini</button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function Workspace() {
  const { id } = useParams<{ id: string }>();
  const { data: cust, error, loading, reload } = useLoad(() => api<Customization>(`/customizations/${id}`), id);
  if (loading) return <p>Memuat…</p>;
  if (error || !cust) return <Notice tone="error">{error ?? "Desain tidak ditemukan."}</Notice>;
  return (
    <div className="grid max-w-3xl gap-[clamp(56px,8vw,96px)]">
      <p className="text-lg">{cust.template.name} · revisi desain {cust.current_revision}</p>
      <Section title="Desain"><DesignOptions cust={cust} onChanged={reload} /><PromptBox cust={cust} onChanged={reload} /></Section>
      <Section title="Ukuran badan"><Measurements cust={cust} onChanged={reload} /></Section>
      <Section title="Kebutuhan kain"><EstimateBox cust={cust} onChanged={reload} /></Section>
      <Section title="Ilustrasi"><PreviewBox cust={cust} /></Section>
      <Section title="Coba di badanmu (3D)"><AvatarBox cust={cust} /></Section>
      <Section title="Pilih penjahit"><Tailors cust={cust} /></Section>
    </div>
  );
}

export default function CustomizePage() {
  return (
    <Page>
      <p className="mb-2 mt-6 text-base"><Link href="/gallery" className="link">← Gallery</Link></p>
      <h1 className="t-display mb-10" style={{ fontSize: "clamp(40px, 7vw, 112px)" }}>Rancang bajumu</h1>
      <RequireAuth><Workspace /></RequireAuth>
    </Page>
  );
}
