"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Check, ChevronDown, LoaderCircle, Scissors, Sparkles } from "lucide-react";
import { GarmentDrawing, ModelChoices, STUDIO_STEPS, StudioCanvas, StudioLoading, StudioShell, type StudioTemplate } from "@/components/Studio";
import { AvatarViewer } from "@/components/AvatarViewer";
import { PhotoMeasure } from "@/components/PhotoMeasure";
import { PhotoTryOn } from "@/components/PhotoTryOn";
import { AddressForm } from "@/components/AddressForm";
import type { Listing } from "@/components/ListingCard";
import { Field, Notice, useAction, useLoad } from "@/components/ui";
import { api, fileUrl, idr } from "@/lib/api";
import { DIM_LABEL, OPTION_LABEL, VALUE_LABEL, label, layoutText, optionText, type MotifLayout, type OptionDef } from "@/lib/design";

type Customization = {
  id: string; listing_id: string; template: { code: string; name: string; required_dimensions: string[] };
  current_revision: number; state: Record<string, string | number | MotifLayout>;
  open_clarifications: { id: string; field: string; question: string; choices: string[] }[];
  measurement_set: { id: string; status: string; revision: number } | null;
  material_estimate: { id: string; stale: boolean } | null; ready_for_tailor_validation: boolean;
};
type Proposal = {
  proposal_id: string;
  changes: { field: string; value: unknown; from: unknown; status: string }[];
  unsupported_requests: { text: string; reason: string }[];
  clarifications: { id: string; field: string; text: string; question: string; choices: string[]; direction: number }[];
  fallback: string | null;
};
type Estimate = {
  id: string; stale: boolean; stale_reasons: string[]; notice: string;
  result: { fits: boolean; required_length_cm: number; breakdown_cm: Record<string, number>; assumptions: string[]; selling_unit: string; purchase_quantity: string; surplus_m: string; stock_ok: boolean };
};
type Preview = { id: string; status: string; url: string | null; warnings: string[]; label: string; method: string | null; design_revision: number };
type Tailor = { tailor_id: string; shop_name: string; city: string; province: string; experience_years: number; base_rate_idr: number; lead_time_days: number; reasons: string[] };
type Address = { id: string; label: string; recipient_name: string; line1: string; city: string };
type MSet = { id: string; height_cm: number | null; status: string; revision: number; notice: string; values: { key: string; value_cm: number | null; source: string }[] };

const H = { fontFamily: "var(--font-hanken)" } as const;
const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="studio-section"><div className="studio-panel-heading"><span className="studio-eyebrow">LANGKAH {String(STUDIO_STEPS.findIndex((s) => s.title === title) + 1).padStart(2, "0")} / {String(STUDIO_STEPS.length).padStart(2, "0")}</span><h2>{title}</h2></div>{children}</section>
);

type TemplateDetails = { options: Record<string, OptionDef>; notice: string };

function DesignOptions({ cust, initialTemplate, onChanged, onDirtyChange }: { cust: Customization; initialTemplate: TemplateDetails | null; onChanged: () => void; onDirtyChange: (dirty: boolean) => void }) {
  const tpl = useLoad(() => initialTemplate ? Promise.resolve(initialTemplate) : api<TemplateDetails>(`/garment-templates/${cust.template.code}`), cust.template.code);
  const act = useAction();
  const [draft, setDraft] = useState<Record<string, string | number>>({});
  const template = tpl.data ?? initialTemplate;
  // the motif layout has its own controls (FabricMapBox); here only the plain options
  const options = Object.fromEntries(Object.entries(template?.options ?? {}).filter(([, d]) => d.type !== "layout"));
  const changed = Object.fromEntries(Object.entries(draft).filter(([k, v]) => String(v) !== String(cust.state[k])));
  const dirty = Object.keys(changed).length > 0;
  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  const groups = [
    { title: "Detail pakaian", number: "01", entries: Object.entries(options).filter(([key, def]) => def.type === "enum" && key !== "motif_placement") },
    { title: "Motif & panjang", number: "02", entries: Object.entries(options).filter(([key, def]) => def.type === "number" || key === "motif_placement") },
  ];
  return (
    <div className="grid gap-5">
      {tpl.error && <Notice tone="error">{tpl.error}</Notice>}
      {tpl.loading && !template && <p role="status">Memuat pilihan desain…</p>}
      {groups.filter((group) => group.entries.length > 0).map((group) => <div className="studio-option-group" key={group.title}>
      <div className="studio-group-heading"><h3>{group.title}</h3><span>{group.number}</span></div>
      <div className="studio-fields">
        {group.entries.map(([key, def]) => {
          if (def.type === "layout") return null;
          const value = draft[key] ?? (cust.state[key] as string | number | undefined) ?? def.default;
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
      </div>)}
      {template?.notice && <p className="studio-fine-print">{template.notice}</p>}
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <button className="btn w-fit" disabled={act.busy || Object.keys(changed).length === 0}
        onClick={async () => { const r = await act.run(() => api(`/customizations/${cust.id}/revisions`, { body: { expected_design_revision: cust.current_revision, changes: changed } })); if (r) { setDraft({}); onChanged(); } }}>
        {act.busy ? "Menyimpan…" : "Simpan perubahan desain"}
      </button>
    </div>
  );
}

type Region = { id: string; kind: "zone" | "motif"; label: string; box: number[]; repeats: number | null };
type FabricMap = { id: string; status: string; error: string | null; regions: Region[]; photo_url: string; label: string };

/** The listing photo with where its zones and motifs sit, so the buyer knows what to name in a prompt. */
function FabricMapBox({ cust, onChanged }: { cust: Customization; onChanged: () => void }) {
  const act = useAction();
  const map = useLoad(() => api<FabricMap | null>(`/listings/${cust.listing_id}/fabric-map`), cust.listing_id);
  const m = map.data;
  const pending = m?.status === "pending";
  const { reload } = map;
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(reload, 2500);
    return () => clearInterval(t);
  }, [pending, reload]);
  const layout = cust.state.motif_layout as MotifLayout | undefined;
  const hasLayout = !!layout && (Object.keys(layout.panels ?? {}).length > 0 || (layout.avoid ?? []).length > 0);
  const usable = (m?.regions ?? []).filter((r) => r.label !== "rumbai");
  return (
    <div className="grid gap-4">
      <h3 className="text-xl font-medium" style={H}>Peta motif kain</h3>
      <p className="text-base">Petakan dulu bagian-bagian kain asli ini (kepala kain, badan kain, motif-motifnya). Setelah itu kamu bisa menulis bagian kain mana yang ditaruh di bagian baju mana.</p>
      {(!m || m.status === "failed") && (
        <button className="btn btn-quiet w-fit" disabled={act.busy} onClick={async () => { const r = await act.run(() => api(`/listings/${cust.listing_id}/fabric-map`, { method: "POST" })); if (r) reload(); }}>
          {m?.status === "failed" ? "Coba petakan lagi" : "Petakan motif kain"}
        </button>
      )}
      {act.error && <Notice tone="error">{act.error}</Notice>}
      {m?.status === "failed" && <Notice tone="error">Peta kain gagal dibuat{m.error ? `: ${m.error}` : "."}</Notice>}
      {pending && <p role="status">Kain sedang dipetakan…</p>}
      {m && (m.status === "estimated" || m.status === "confirmed") && (
        <div className="grid gap-3 sm:grid-cols-[minmax(0,260px)_1fr] sm:items-start">
          <div className="relative">
            <img src={fileUrl(m.photo_url)} alt="Foto kain dengan bagian-bagian yang dipetakan" className="block w-full" />
            {m.regions.map((r) => (
              <span key={r.id} title={r.label}
                className={`absolute ${r.kind === "zone" ? "border border-dashed border-surface" : "border-2 border-ink"}`}
                style={{ left: `${r.box[0] * 100}%`, top: `${r.box[1] * 100}%`, width: `${(r.box[2] - r.box[0]) * 100}%`, height: `${(r.box[3] - r.box[1]) * 100}%` }}>
                <span className={`absolute left-0 top-0 px-1 text-xs leading-5 ${r.kind === "zone" ? "bg-surface text-ink" : "bg-ink text-bg"}`}>{r.label}</span>
              </span>
            ))}
          </div>
          <div className="grid gap-2 text-base">
            <p>Bagian kain yang bisa kamu sebut:</p>
            <ul className="flex flex-wrap gap-2 p-0">{usable.map((r) => <li key={r.id} className="list-none bg-surface px-3 py-1">{r.label}{r.repeats ? ` ×${r.repeats}` : ""}</li>)}</ul>
            <p className="text-muted">{m.label}</p>
          </div>
        </div>
      )}
      {hasLayout && (
        <div className="flex flex-wrap items-center gap-3 bg-surface p-4 text-base">
          <span>Tata letak kain: {layoutText(layout)}</span>
          <button className="btn btn-quiet" disabled={act.busy} onClick={async () => { const r = await act.run(() => api(`/customizations/${cust.id}/revisions`, { body: { expected_design_revision: cust.current_revision, changes: { motif_layout: {} } } })); if (r) onChanged(); }}>Kembalikan otomatis</button>
        </div>
      )}
    </div>
  );
}

function PromptBox({ cust, onChanged }: { cust: Customization; onChanged: () => void }) {
  const act = useAction();
  const [prompt, setPrompt] = useState("");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [picks, setPicks] = useState<Record<string, string>>({});
  return (
    <div className="studio-prompt grid gap-4">
      <div className="studio-group-heading"><h3><Sparkles size={16} /> Ceritakan idemu</h3><span>03</span></div>
      <Field label="Ceritakan perubahan dengan kalimat biasa" hint="Contoh: tambah saku dada kiri, kancing kayu, pendekkan hem 3 cm. Setelah kain dipetakan: motif manusianya taruh di dada, burung di bawahan, kepala kainnya jangan dipakai. Sistem hanya menerapkan opsi yang didukung pola ini.">
        <textarea className="field" placeholder="Misalnya, tambahkan saku dada kiri dan kancing kayu…" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
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
            <ul className="grid list-disc gap-1 pl-5">{proposal.changes.map((c) => <li key={c.field}>{label(OPTION_LABEL, c.field)}: {optionText(c.from)} → {optionText(c.value)}</li>)}</ul>
          ) : <p className="text-base">Belum ada perubahan yang bisa diterapkan.</p>}
          {proposal.clarifications.map((c) => (
            <Field key={c.id} label={`${c.question} (“${c.text}”)`}>
              <select className="field" value={picks[c.id] ?? ""} onChange={(e) => setPicks({ ...picks, [c.id]: e.target.value })}>
                <option value="">Pilih…</option>
                {c.choices.map((v) => <option key={v} value={v}>{OPTION_LABEL[v] ?? label(VALUE_LABEL, v)}</option>)}
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

type DesignRevision = { revision: number; source: string; state: Record<string, string | number | MotifLayout>; prompt_text: string | null; created_at: string };

function RevisionHistory({ cust, onChanged }: { cust: Customization; onChanged: () => void }) {
  const versions = useLoad(() => api<DesignRevision[]>(`/customizations/${cust.id}/revisions`), `${cust.id}-${cust.current_revision}`);
  const act = useAction();
  return <details className="studio-history"><summary>Riwayat desain <span>Revisi {cust.current_revision} <ChevronDown size={15} /></span></summary>
    {versions.error && <Notice tone="error">{versions.error}</Notice>}{act.error && <Notice tone="error">{act.error}</Notice>}
    <ul className="mt-4 grid list-none gap-4 p-0">{versions.data?.map((v) => <li key={v.revision} className="grid gap-2 border-t border-current/20 pt-4">
      <p>Revisi {v.revision}{v.revision === cust.current_revision && " · aktif"}</p>
      {v.prompt_text && <p className="text-base">Permintaan: {v.prompt_text}</p>}
      <ul className="list-disc pl-5 text-base">{Object.entries(v.state).map(([key, value]) => <li key={key}>{label(OPTION_LABEL, key)}: {optionText(value)}</li>)}</ul>
      {v.revision !== cust.current_revision && <button className="btn btn-quiet w-fit" disabled={act.busy} onClick={async () => {
        const result = await act.run(() => api(`/customizations/${cust.id}/revisions`, { body: { expected_design_revision: cust.current_revision, revert_to_revision: v.revision } }));
        if (result) onChanged();
      }}>Gunakan versi ini</button>}
    </li>)}</ul>
  </details>;
}

function Measurements({ cust, onChanged, onFrontUploaded }: { cust: Customization; onChanged: () => void; onFrontUploaded: (id: string) => void }) {
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
      <PhotoMeasure custId={cust.id} onMeasured={() => { existing.reload(); onChanged(); }} onFrontUploaded={onFrontUploaded} />
      <p className="text-base">Ukur dengan meteran dan isi dalam sentimeter, atau koreksi hasil dari foto. Ukuran Anda hanya dibagikan ke penjahit yang Anda pilih.</p>
      {set?.notice && <Notice>{set.notice}</Notice>}
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

function PreviewBox({ cust, model, listing, loading, dirty }: { cust: Customization | null; model?: { code: string; name: string }; listing: Listing | null; loading: boolean; dirty: boolean }) {
  const act = useAction();
  const [previewState, setPreview] = useState<{ customizationId: string; data: Preview } | null>(null);
  const preview = previewState?.customizationId === cust?.id ? previewState?.data : null;
  const pending = preview && ["queued", "processing"].includes(preview.status);
  useEffect(() => {
    if (!preview || !pending) return;
    const t = setInterval(async () => { try {
      const data = await api<Preview>(`/previews/${preview.id}`);
      setPreview((current) => current?.data.id === data.id ? { ...current, data } : current);
    } catch { /* retry on next tick */ } }, 2500);
    return () => clearInterval(t);
  }, [preview, pending]);
  const current = preview?.url && preview.design_revision === cust?.current_revision && preview.status !== "stale" && !pending && preview.status !== "failed" ? { url: preview.url, label: preview.label } : null;
  return (
    <StudioCanvas listing={listing} loading={loading} model={model ?? cust?.template} illustration={current} toolbar={cust &&
      <button className="btn btn-quiet" disabled={act.busy || !!pending || dirty} onClick={async () => { const p = await act.run(() => api<Preview>(`/customizations/${cust.id}/product-previews`, { method: "POST" })); if (p) setPreview({ customizationId: cust.id, data: p }); }}>{pending || act.busy ? <LoaderCircle size={16} className="animate-spin" /> : <Sparkles size={16} />}{pending ? "Membuat ilustrasi…" : "Buat ilustrasi desain"}</button>
    }>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      {pending && <p role="status">Ilustrasi sedang dibuat…</p>}
      {preview?.status === "failed" && <Notice tone="error">Ilustrasi gagal dibuat.</Notice>}
      {preview && (preview.design_revision !== cust?.current_revision || preview.status === "stale") && <Notice>Desain berubah. Buat ulang ilustrasi untuk revisi terbaru.</Notice>}
      {preview?.warnings.map((w) => <p key={w} className="text-base text-muted">{w}</p>)}
    </StudioCanvas>
  );
}

/** A preview job: polled until the worker has finished it, and read again whenever `refreshKey`
 * changes (a new design or measurement revision can make it stale). */
function usePreview(refreshKey: string) {
  const [preview, setPreview] = useState<Preview | null>(null);
  const pending = !!preview && ["queued", "processing"].includes(preview.status);
  const id = preview?.id;
  useEffect(() => {
    if (!id) return;
    api<Preview>(`/previews/${id}`).then(setPreview).catch(() => { /* keep the last known state */ });
  }, [id, refreshKey]);
  useEffect(() => {
    if (!preview || !pending) return;
    const t = setInterval(async () => { try { setPreview(await api<Preview>(`/previews/${preview.id}`)); } catch { /* retry on next tick */ } }, 2500);
    return () => clearInterval(t);
  }, [preview, pending]);
  return { preview, setPreview, pending };
}

const GENDERS = [["neutral", "Netral"], ["female", "Perempuan"], ["male", "Laki-laki"]] as const;

function AvatarBox({ cust }: { cust: Customization }) {
  const act = useAction();
  const { preview, setPreview, pending } = usePreview(`${cust.current_revision}-${cust.measurement_set?.revision ?? 0}`);
  const [gender, setGender] = useState("neutral");
  const mset = cust.measurement_set;
  const make = async () => {
    if (!mset) return;
    const p = await act.run(() => api<Preview>(`/customizations/${cust.id}/avatar-previews`, { body: { measurement_set_id: mset.id, gender } }));
    if (p) setPreview(p);
  };
  // warnings start with a machine code ("avatar_mismatch:back_length: ..."); show the sentence after it
  const notes = preview?.warnings.map((w) => w.replace(/^[a-z_]+(:[a-z0-9_]+)?: /, "")) ?? [];
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
      <Field label="Alamat pengiriman baju">
        <select className="field" value={chosen} onChange={(e) => setAddrId(e.target.value)}>
          {addresses.data?.map((a) => <option key={a.id} value={a.id}>{a.label}: {a.recipient_name}, {a.line1}, {a.city}</option>)}
        </select>
      </Field>
      <AddressForm onCreated={(id) => { setAddrId(id); addresses.reload(); }} />
      <p className="text-base">Penjahit menerima desain, ilustrasi produk, ukuran, kebutuhan kain, dan alamat. Foto badan dan Fit On tidak dikirim; penjual menerima rincian kain yang diperlukan.</p>
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
                <Link href={`/tailors/${t.tailor_id}`} className="link w-fit text-base">Lihat profil penjahit</Link>
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

export function StudioWorkspace({ initialListingId, initialCustomizationId }: { initialListingId?: string; initialCustomizationId?: string }) {
  const [customizationId, setCustomizationId] = useState(initialCustomizationId);
  const [frontPhotoId, setFrontPhotoId] = useState<string>();
  const [step, setStep] = useState(initialCustomizationId ? 1 : 0);
  const [selected, setSelected] = useState("");
  const [initialTemplate, setInitialTemplate] = useState<TemplateDetails | null>(null);
  const [dirty, setDirty] = useState(false);
  const action = useAction();
  const { data: cust, error, loading, reload, setData } = useLoad(() => customizationId ? api<Customization>(`/customizations/${customizationId}`) : Promise.resolve(null), customizationId ?? "new");
  const listingId = initialListingId ?? cust?.listing_id;
  const listing = useLoad(() => listingId ? api<Listing>(`/listings/${listingId}`, { token: null }) : Promise.resolve(null), listingId ?? "");
  const templates = useLoad(() => listingId ? api<StudioTemplate[]>(`/listings/${listingId}/templates`, { token: null }) : Promise.resolve(null), listingId ?? "");
  if ((loading && !cust) || (!listing.data && !listing.error && !error)) return <StudioLoading />;
  if (error || listing.error || !listing.data) return <Notice tone="error">{error ?? listing.error ?? "Kain tidak ditemukan."}</Notice>;
  const model = templates.data?.find((template) => template.code === selected) ?? (selected ? undefined : cust?.template);
  const goToStep = (next: number) => {
    setStep(next);
  };
  const startDesign = async () => {
    if (!model || !listingId) return;
    const result = await action.run(async () => {
      const template = await api<TemplateDetails>(`/garment-templates/${model.code}`);
      const customization = cust?.template.code === model.code ? cust : await api<Customization>("/customizations", { body: { listing_id: listingId, template_code: model.code } });
      return { template, customization };
    });
    if (!result) return;
    setInitialTemplate(result.template);
    setData(result.customization);
    setCustomizationId(result.customization.id);
    if (result.customization.id !== cust?.id) {
      setDirty(false);
      setFrontPhotoId(undefined);
    }
    setStep(1);
    // Keep this mounted workspace and its scroll position; refresh still opens the saved design URL.
    window.history.replaceState(null, "", `/customize/${result.customization.id}`);
  };
  return (
    <StudioShell listingId={listing.data.id} step={step} onStep={cust && !action.busy ? goToStep : undefined} canvas={<PreviewBox cust={step === 0 ? null : cust} model={step === 0 ? model : undefined} listing={listing.data} loading={listing.loading} dirty={dirty} />} footer={step === 0 ? <>
      <span className="studio-save-status"><Scissors size={16} /> {model ? model.name : "Pilih model untuk memulai"}</span>
      <button className="btn" disabled={!model || !("compatible" in model ? model.compatible : true) || action.busy || !listing.data.stock.in_stock} onClick={startDesign}>{action.busy ? "Menyiapkan desain…" : "Lanjut ke desain"}<ArrowRight size={16} /></button>
    </> : cust && <>
      <span className="studio-save-status"><Check size={15} /><span>{dirty ? "Perubahan belum disimpan" : "Desain tersimpan"} <small>Revisi {cust.current_revision}</small></span></span>
      <div className="studio-bottom-actions"><button type="button" className="btn btn-quiet" onClick={() => goToStep(step - 1)}><ArrowLeft size={15} /> Sebelumnya</button>
      {step < STUDIO_STEPS.length - 1 && <button type="button" className="btn" disabled={dirty} onClick={() => goToStep(step + 1)}>{["Lanjut ke desain", "Lanjut ke ukuran", "Lanjut ke kebutuhan kain", "Lanjut ke penjahit"][step]} <ArrowRight size={15} /></button>}</div>
    </>}>
          <div hidden={step !== 0}><Section title="Pilih model"><p className="text-base text-muted">Satu kain, banyak kemungkinan. Mulai dari model favoritmu.</p><div className="studio-group-heading"><h3>Pilih model pakaian</h3><span>01</span></div>
            {templates.error && <Notice tone="error">{templates.error}</Notice>}
            {templates.loading && <p role="status">Memuat pilihan model…</p>}
            <ModelChoices templates={templates.data ?? []} selected={model?.code ?? ""} disabled={action.busy || !listing.data.stock.in_stock} onSelect={setSelected} />
            <div className="studio-start-tip"><Scissors size={19} /><p><strong>Sentuhanmu di setiap detail</strong>Setelah memilih model, sesuaikan kerah, saku, kancing, dan penempatan motif sesuai keinginanmu.</p></div>
            {templates.data?.length === 0 && <p>Model pakaian belum tersedia.</p>}
            {!listing.data.stock.in_stock && <Notice tone="error">Kain ini sedang tidak tersedia.</Notice>}
            {action.error && <Notice tone="error">{action.error}</Notice>}
          </Section></div>
          {cust && <div key={cust.id} className="studio-design-panels">
          <div hidden={step !== 1}><Section title="Desain"><div className="studio-selected-model"><GarmentDrawing code={cust.template.code} /><div><span>MODEL PILIHANMU</span><strong>{cust.template.name}</strong><button type="button" onClick={() => setStep(0)}>Pilih model lain <ArrowRight size={12} /></button></div><span className="studio-selected-check"><Check size={15} /></span></div><DesignOptions cust={cust} initialTemplate={initialTemplate} onChanged={reload} onDirtyChange={setDirty} /><FabricMapBox cust={cust} onChanged={reload} /><PromptBox cust={cust} onChanged={reload} /><RevisionHistory cust={cust} onChanged={reload} /></Section></div>
          <div hidden={step !== 2}><Section title="Ukuran & Fit On"><Measurements cust={cust} onChanged={reload} onFrontUploaded={setFrontPhotoId} /><PhotoTryOn key={frontPhotoId ?? "no-photo"} custId={cust.id} revision={cust.current_revision} frontPhotoId={frontPhotoId} /><div className="studio-option-group"><div className="studio-group-heading"><h3>Coba di badanmu (3D)</h3></div><AvatarBox cust={cust} /></div></Section></div>
          <div hidden={step !== 3}><Section title="Kebutuhan kain"><EstimateBox cust={cust} onChanged={reload} /></Section></div>
          <div hidden={step !== 4}><Section title="Pilih penjahit"><Tailors cust={cust} /></Section></div>
          </div>}
    </StudioShell>
  );
}
