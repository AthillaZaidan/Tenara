"use client";

import { useEffect, useRef, useState } from "react";
import { api, fileUrl } from "@/lib/api";
import { DIM_LABEL, label } from "@/lib/design";
import { Field, Notice, useAction } from "./ui";

type Ring = { key: string; cx: number; cy: number; rx: number; ry: number };
type Line = { key: string; points: [number, number][] };
type View = { frame: [number, number]; rings: Ring[]; lines: Line[]; photo_url: string };
type Job = {
  job_id: string; status: string; error: string | null;
  output: { method?: string; warnings?: string[]; measurement_set_id?: string } | null;
  measurement_set: { id: string; values: { key: string; value_cm: number | null; source: string }[] } | null;
  visual: { front?: View; side?: View } | null;
};
type Notice_ = { text: string; default_retention_minutes: number; guidance: string[] };

const COLOR: Record<string, string> = {
  neck_circumference: "#ffc400", chest_circumference: "#ff4081", waist_circumference: "#00c8ff",
  hip_circumference: "#7c4dff", shoulder_width: "#00e676", sleeve_length: "#ff9100", back_length: "#00e676",
};
const RUNNING = ["queued", "processing"];
const storeKey = (custId: string) => `tenara.measure.${custId}`;

function remember(custId: string, jobId: string | null) {
  try {
    if (jobId) window.localStorage.setItem(storeKey(custId), jobId);
    else window.localStorage.removeItem(storeKey(custId));
  } catch {
    /* private mode: the drawing simply will not come back after a reload */
  }
}

function recall(custId: string): string | null {
  try {
    return window.localStorage.getItem(storeKey(custId));
  } catch {
    return null;
  }
}

/** One photo with the measurement rings and lines drawn over it (geometry from the server, in photo pixels). */
function MeasuredPhoto({ view, title }: { view: View; title: string }) {
  const [w, h] = view.frame;
  const stroke = Math.max(3, Math.round(h / 260));
  return (
    <figure className="grid gap-2">
      <div className="relative overflow-hidden bg-surface">
        <img src={fileUrl(view.photo_url)} alt={title} className="block w-full" />
        <svg viewBox={`0 0 ${w} ${h}`} className="absolute inset-0 h-full w-full" aria-hidden="true">
          {view.rings.map((r) => (
            <g key={r.key} stroke={COLOR[r.key]} fill="none">
              {/* far half of the loop dashed, near half solid, so a level ring reads as a loop */}
              <path d={`M ${r.cx - r.rx} ${r.cy} A ${r.rx} ${r.ry} 0 0 1 ${r.cx + r.rx} ${r.cy}`} strokeWidth={stroke / 2} strokeDasharray={`${stroke * 2} ${stroke * 2}`} opacity={0.7} />
              <path d={`M ${r.cx - r.rx} ${r.cy} A ${r.rx} ${r.ry} 0 0 0 ${r.cx + r.rx} ${r.cy}`} strokeWidth={stroke} />
            </g>
          ))}
          {view.lines.map((l) => (
            <g key={l.key} stroke={COLOR[l.key]} fill={COLOR[l.key]}>
              <line x1={l.points[0][0]} y1={l.points[0][1]} x2={l.points[1][0]} y2={l.points[1][1]} strokeWidth={stroke} />
              {l.points.map(([x, y], i) => <circle key={i} cx={x} cy={y} r={stroke * 1.6} />)}
            </g>
          ))}
        </svg>
      </div>
      <figcaption className="t-small text-muted">{title}</figcaption>
    </figure>
  );
}

function Result({ job }: { job: Job }) {
  const values = job.measurement_set?.values ?? [];
  const warnings = (job.output?.warnings ?? []).filter((w) => w !== "buyer_review_required").map((w) => w.split(": ").slice(1).join(": ") || w);
  return (
    <div className="grid gap-5">
      {job.visual && (
        <div className="grid gap-4 sm:grid-cols-2">
          {job.visual.front && <MeasuredPhoto view={job.visual.front} title="Tampak depan" />}
          {job.visual.side && <MeasuredPhoto view={job.visual.side} title="Tampak samping" />}
        </div>
      )}
      <ul className="grid list-none gap-2 p-0 text-base sm:grid-cols-2">
        {values.map((v) => (
          <li key={v.key} className="flex items-center gap-3">
            <span className="inline-block h-3 w-3 shrink-0" style={{ background: COLOR[v.key] ?? "currentColor" }} />
            <span>{label(DIM_LABEL, v.key)}</span>
            <span className="ml-auto font-medium">{v.value_cm != null ? `${v.value_cm} cm` : "isi manual"}</span>
          </li>
        ))}
      </ul>
      <Notice>
        Ini perkiraan dari foto, bukan hasil meteran. Angkanya sudah masuk ke form ukuran di bawah: cek, koreksi bila perlu, lalu konfirmasi.
        {warnings.length > 0 && <span className="mt-2 block">{warnings.join(" ")}</span>}
      </Notice>
    </div>
  );
}

/** Buyer-side: measure from a front and a side photo (SMPL-X fit on the server), then review in the form. */
export function PhotoMeasure({ custId, onMeasured, onFrontUploaded }: { custId: string; onMeasured: () => void; onFrontUploaded?: (id: string) => void }) {
  const act = useAction();
  const [open, setOpen] = useState(false);
  const [notice, setNotice] = useState<Notice_ | null>(null);
  const [agreed, setAgreed] = useState(false);
  const [front, setFront] = useState<File | null>(null);
  const [side, setSide] = useState<File | null>(null);
  const [height, setHeight] = useState("");
  const [gender, setGender] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [pollError, setPollError] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const poll = async (jobId: string) => {
    try {
      const j = await api<Job>(`/body-measurements/${jobId}`);
      setPollError("");
      setJob(j);
      if (RUNNING.includes(j.status)) {
        timer.current = setTimeout(() => poll(jobId), 2000);
      } else if (j.measurement_set) {
        await api(`/customizations/${custId}/measurement-set`, { body: { measurement_set_id: j.measurement_set.id } });
        onMeasured();
      }
    } catch {
      setPollError("Status pengukuran belum dapat dimuat. Coba periksa lagi.");
    }
  };

  useEffect(() => {
    const saved = recall(custId);
    if (saved) poll(saved);
    return () => { if (timer.current) clearTimeout(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [custId]);

  const start = async () => {
    if (!notice) setNotice(await api<Notice_>("/photo-consent-notice"));
    setOpen(true);
  };

  const submit = async () => {
    const r = await act.run(async () => {
      const consent = await api<{ id: string }>("/photo-consents", { body: {} });
      const upload = async (file: File) => {
        const form = new FormData();
        form.append("file", file);
        form.append("consent_id", consent.id);
        return api<{ id: string }>("/body-photos", { form });
      };
      const f = await upload(front!);
      onFrontUploaded?.(f.id);
      const s = side ? await upload(side) : null;
      return api<{ job_id: string }>("/body-measurements/estimate", {
        body: { body_photo_id: f.id, side_photo_id: s?.id ?? null, height_cm: Number(height), gender: s ? gender : null, customization_id: custId },
      });
    });
    if (r) {
      remember(custId, r.job_id);
      setJob({ job_id: r.job_id, status: "queued", error: null, output: null, measurement_set: null, visual: null });
      poll(r.job_id);
    }
  };

  const running = job && RUNNING.includes(job.status);
  const ready = agreed && front && Number(height) >= 100 && Number(height) <= 230 && (!side || gender);

  return (
    <div className="grid gap-5">
      {!open && !job && (
        <div className="grid gap-3">
          <p className="text-base">Perkirakan sebagian ukuran dari foto depan. Foto samping opsional dapat membantu estimasi tambahan bila model tersedia. Hasilnya perlu diperiksa dan dikoreksi.</p>
          <button className="btn btn-quiet w-fit" onClick={() => act.run(start)}>Ukur dari foto</button>
        </div>
      )}
      {open && !job && (
        <div className="grid gap-5 bg-surface p-5">
          <div className="grid gap-2 text-base">
            <p className="font-medium">Cara memotret</p>
            <ul className="grid list-disc gap-1 pl-5">
              {notice?.guidance.map((item) => <li key={item}>{item}</li>)}
              <li>HP tegak, setinggi pinggang, jarak 2,5 sampai 3 meter, tidak menunduk atau mendongak.</li>
              <li>Seluruh badan masuk, dari ujung kepala sampai telapak kaki.</li>
              <li><span className="font-medium">Foto depan:</span> menghadap kamera, lengan dibuka seperti huruf A.</li>
              <li><span className="font-medium">Foto samping:</span> badan menyamping penuh, pandangan lurus ke depan, lengan lurus ke bawah.</li>
              <li>Baju pas badan dan latar polos. Baju longgar membuat lingkar terbaca lebih besar.</li>
            </ul>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Foto tampak depan"><input type="file" accept="image/*" className="field" onChange={(e) => setFront(e.target.files?.[0] ?? null)} /></Field>
            <Field label="Foto tampak samping (opsional)"><input type="file" accept="image/*" className="field" onChange={(e) => setSide(e.target.files?.[0] ?? null)} /></Field>
            <Field label="Tinggi badan (cm)" hint="Dipakai sebagai skala; isi setepat mungkin."><input className="field" inputMode="decimal" value={height} onChange={(e) => setHeight(e.target.value)} /></Field>
            <Field label="Model tubuh">
              <select className="field" value={gender} onChange={(e) => setGender(e.target.value)}>
                <option value="">Pilih…</option>
                <option value="female">Perempuan</option>
                <option value="male">Laki-laki</option>
              </select>
            </Field>
          </div>
          {notice && (
            <label className="flex items-start gap-3 text-base">
              <input type="checkbox" className="mt-1" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
              <span>{notice.text} Masa simpan bawaan: {notice.default_retention_minutes} menit.</span>
            </label>
          )}
          {act.error && <Notice tone="error">{act.error}</Notice>}
          <div className="flex flex-wrap gap-3">
            <button className="btn" disabled={act.busy || !ready} onClick={submit}>{act.busy ? "Mengunggah…" : "Ukur sekarang"}</button>
            <button className="btn btn-quiet" disabled={act.busy} onClick={() => setOpen(false)}>Batal</button>
          </div>
        </div>
      )}
      {running && <Notice>Sedang mengukur dari foto. Biasanya 10 sampai 30 detik.</Notice>}
      {pollError && <div className="grid gap-2"><Notice tone="error">{pollError}</Notice><button className="btn btn-quiet w-fit" onClick={() => { const id = job?.job_id ?? recall(custId); if (id) void poll(id); }}>Periksa status lagi</button></div>}
      {job?.status === "failed" && (
        <div className="grid gap-3">
          <Notice tone="error">Foto belum bisa dipakai: {job.error}</Notice>
          <button className="btn btn-quiet w-fit" onClick={() => { remember(custId, null); setJob(null); setOpen(true); }}>Coba foto lain</button>
        </div>
      )}
      {job && job.measurement_set && <Result job={job} />}
      {job && !running && (
        <button className="link w-fit text-base" onClick={() => { remember(custId, null); setJob(null); setOpen(true); }}>Ukur ulang dari foto lain</button>
      )}
    </div>
  );
}
