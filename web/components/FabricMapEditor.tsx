"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Map as MapIcon, Plus, RotateCcw, Trash2 } from "lucide-react";
import { WorkspacePanel } from "@/components/PartnerWorkspace";
import { Field, Notice, useAction, useLoad } from "@/components/ui";
import { api, fileUrl } from "@/lib/api";

type Region = { id: string; kind: "zone" | "motif"; label: string; box: [number, number, number, number]; repeats: number | null };
type FabricMap = { id: string; status: string; error: string | null; revision: number; regions: Region[]; photo_url: string; label: string };

// the zone names the scan uses, so a corrected map reads the same in prompts and for the tailor
const ZONES = ["badan kain", "kepala kain", "pinggiran", "tumpal", "rumbai"];
const MIN = 0.03; // smallest box side, as a fraction of the photo
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

type Drag = { id: string; mode: "move" | "resize"; x: number; y: number; box: Region["box"] };

/** Moves or resizes one box by a pointer delta (fractions of the photo), keeping it inside the photo. */
function moved(box: Region["box"], mode: Drag["mode"], dx: number, dy: number): Region["box"] {
  const [x0, y0, x1, y1] = box;
  if (mode === "resize") return [x0, y0, clamp(x1 + dx, x0 + MIN, 1), clamp(y1 + dy, y0 + MIN, 1)];
  const w = x1 - x0, h = y1 - y0;
  const nx = clamp(x0 + dx, 0, 1 - w), ny = clamp(y0 + dy, 0, 1 - h);
  return [nx, ny, nx + w, ny + h];
}

const round = (box: Region["box"]) => box.map((v) => Math.round(v * 1000) / 1000) as Region["box"];

/** The merchant checks the AI's map of their fabric photo: drags and resizes boxes, renames, adds or
 * removes parts, then confirms. Buyers name these parts in prompts; the tailor sees them on the order. */
export function FabricMapEditor({ listingId, hasPhoto }: { listingId: string; hasPhoto: boolean }) {
  const map = useLoad(() => api<FabricMap | null>(`/merchant/listings/${listingId}/fabric-map`), listingId);
  const act = useAction();
  const m = map.data;
  const [draft, setDraft] = useState<Region[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const drag = useRef<Drag | null>(null);
  const frame = useRef<HTMLDivElement>(null);
  const pending = m?.status === "pending";
  const { reload } = map;
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(reload, 2500);
    return () => clearInterval(t);
  }, [pending, reload]);

  const regions = draft ?? m?.regions ?? [];
  const dirty = draft !== null;
  const edit = (next: Region[]) => { setDraft(next); setSaved(false); };
  const update = (id: string, patch: Partial<Region>) => edit(regions.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  const sel = regions.find((r) => r.id === selected) ?? null;

  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current, el = frame.current;
    if (!d || !el) return;
    const rect = el.getBoundingClientRect();
    update(d.id, { box: moved(d.box, d.mode, (e.clientX - d.x) / rect.width, (e.clientY - d.y) / rect.height) });
  };
  const start = (e: React.PointerEvent, r: Region, mode: Drag["mode"]) => {
    e.preventDefault();
    e.stopPropagation();
    setSelected(r.id);
    drag.current = { id: r.id, mode, x: e.clientX, y: e.clientY, box: r.box };
    frame.current?.setPointerCapture(e.pointerId);
  };
  const onKey = (e: React.KeyboardEvent, r: Region) => {
    const step = 0.01;
    const delta = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
    if (!delta) return;
    e.preventDefault();
    update(r.id, { box: moved(r.box, e.shiftKey ? "resize" : "move", delta[0], delta[1]) });
  };
  const add = (kind: Region["kind"]) => {
    const prefix = kind === "zone" ? "z" : "m";
    let n = 1;
    while (regions.some((r) => r.id === `${prefix}${n}`)) n += 1;
    const r: Region = { id: `${prefix}${n}`, kind, label: kind === "zone" ? ZONES.find((z) => !regions.some((x) => x.label === z)) ?? "badan kain" : "motif baru", box: [0.35, 0.35, 0.65, 0.65], repeats: kind === "motif" ? 1 : null };
    edit([...regions, r]);
    setSelected(r.id);
  };
  const confirm = async () => {
    if (!m) return;
    const body = { expected_revision: m.revision, regions: dirty ? regions.map((r) => ({ ...r, box: round(r.box), label: r.label.trim() })) : null };
    const out = await act.run(() => api<FabricMap>(`/merchant/listings/${listingId}/fabric-map`, { method: "PUT", body }));
    if (out) { setDraft(null); setSaved(true); map.setData(out); }
  };
  const blankLabel = regions.some((r) => !r.label.trim());

  return (
    <WorkspacePanel title="Peta motif kain" description="Pembeli menyebut bagian-bagian ini saat merancang baju (misalnya motif manusia di dada). Pastikan letak dan namanya benar." icon={MapIcon}>
      {map.error && <Notice tone="error">{map.error}</Notice>}
      {!hasPhoto && <p>Tambahkan foto kain dulu.</p>}
      {hasPhoto && (!m || m.status === "failed") && (
        <div className="grid gap-2">
          {m?.status === "failed" && <Notice tone="error">Peta kain gagal dibuat{m.error ? `: ${m.error}` : "."}</Notice>}
          <button className="btn btn-quiet w-fit" disabled={act.busy} onClick={async () => { const r = await act.run(() => api(`/merchant/listings/${listingId}/fabric-map`, { method: "POST" })); if (r) reload(); }}>
            {m?.status === "failed" ? "Coba petakan lagi" : "Petakan motif dengan AI"}
          </button>
        </div>
      )}
      {pending && <p role="status">Kain sedang dipetakan AI…</p>}
      {m && (m.status === "estimated" || m.status === "confirmed") && (
        <div className="grid gap-4">
          <p className="text-base">{m.status === "confirmed" && !dirty ? m.label : "Perkiraan AI: geser kotak untuk memindahkan, tarik sudut kanan bawah untuk mengubah ukuran (atau pilih kotak lalu pakai tombol panah; Shift + panah untuk ukuran)."}</p>
          <div ref={frame} className="relative select-none touch-none" onPointerMove={onPointerMove} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }} onPointerDown={() => setSelected(null)}>
            <img src={fileUrl(m.photo_url)} alt="Foto kain yang dipetakan" className="block w-full" draggable={false} />
            {regions.map((r) => {
              const active = r.id === selected;
              const [x0, y0, x1, y1] = r.box;
              return (
                <div key={r.id} role="button" tabIndex={0} aria-label={`${r.label}: geser untuk memindahkan`} aria-pressed={active}
                  onPointerDown={(e) => start(e, r, "move")} onKeyDown={(e) => onKey(e, r)} onFocus={() => setSelected(r.id)}
                  className={`absolute cursor-move ${r.kind === "zone" ? "border border-dashed border-surface" : "border-2 border-ink"} ${active ? "outline outline-2 outline-offset-1 outline-[#c2410c]" : ""}`}
                  style={{ left: `${x0 * 100}%`, top: `${y0 * 100}%`, width: `${(x1 - x0) * 100}%`, height: `${(y1 - y0) * 100}%`, zIndex: active ? 2 : 1 }}>
                  <span className={`absolute left-0 top-0 px-1 text-xs leading-5 ${r.kind === "zone" ? "bg-surface text-ink" : "bg-ink text-bg"}`}>{r.label || "tanpa nama"}</span>
                  <span aria-hidden="true" onPointerDown={(e) => start(e, r, "resize")}
                    className="absolute -bottom-2 -right-2 size-4 cursor-nwse-resize rounded-full border-2 border-bg bg-ink" />
                </div>
              );
            })}
          </div>
          <ul className="grid list-none gap-2 p-0">
            {regions.map((r) => (
              <li key={r.id} className={`grid gap-2 p-3 text-base sm:grid-cols-[7rem_1fr_6rem_auto] sm:items-end ${r.id === selected ? "bg-surface" : ""}`} onClick={() => setSelected(r.id)}>
                <Field label="Jenis">
                  <select className="field" value={r.kind} onChange={(e) => update(r.id, { kind: e.target.value as Region["kind"], repeats: e.target.value === "motif" ? r.repeats ?? 1 : null })}>
                    <option value="zone">Bagian kain</option><option value="motif">Motif</option>
                  </select>
                </Field>
                <Field label="Nama">
                  {r.kind === "zone"
                    ? <select className="field" value={ZONES.includes(r.label) ? r.label : ""} onChange={(e) => update(r.id, { label: e.target.value })}>{!ZONES.includes(r.label) && <option value="">{r.label || "Pilih…"}</option>}{ZONES.map((z) => <option key={z} value={z}>{z}</option>)}</select>
                    : <input className="field" maxLength={40} value={r.label} onChange={(e) => update(r.id, { label: e.target.value })} placeholder="mis. manusia, kuda, burung" />}
                </Field>
                <Field label="Terlihat">
                  <input className="field" type="number" min={1} disabled={r.kind !== "motif"} value={r.repeats ?? ""} onChange={(e) => update(r.id, { repeats: e.target.value ? Math.max(1, Math.round(Number(e.target.value))) : null })} />
                </Field>
                <button type="button" className="btn btn-quiet w-fit" aria-label={`Hapus ${r.label}`} onClick={() => edit(regions.filter((x) => x.id !== r.id))}><Trash2 size={14} /></button>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-3">
            <button type="button" className="btn btn-quiet" onClick={() => add("motif")}><Plus size={14} />Tambah motif</button>
            <button type="button" className="btn btn-quiet" onClick={() => add("zone")}><Plus size={14} />Tambah bagian kain</button>
            {dirty && <button type="button" className="btn btn-quiet" onClick={() => { setDraft(null); setSelected(null); }}><RotateCcw size={14} />Batalkan perubahan</button>}
          </div>
          {sel && <p className="text-base text-muted">Dipilih: {sel.label || "tanpa nama"}.</p>}
          {blankLabel && <Notice tone="error">Setiap bagian perlu nama.</Notice>}
          {act.error && <Notice tone="error">{act.error}</Notice>}
          {saved && <Notice>Peta kain dikonfirmasi. Pembeli kini melihatnya sebagai peta dari penjual.</Notice>}
          <button className="btn w-fit" disabled={act.busy || blankLabel || (m.status === "confirmed" && !dirty)} onClick={confirm}>
            <Check size={14} />{dirty ? "Simpan dan konfirmasi peta" : m.status === "confirmed" ? "Sudah dikonfirmasi" : "Konfirmasi peta apa adanya"}
          </button>
        </div>
      )}
    </WorkspacePanel>
  );
}
