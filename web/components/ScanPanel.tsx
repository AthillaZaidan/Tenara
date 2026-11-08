"use client";

import { api } from "@/lib/api";
import { Notice, useAction } from "./ui";
import { VisualMatch, type VisualMatchData } from "./VisualMatch";

/** Merchant-side: describe the fabric photo and check it against the listing's own Gallery entry (the claim). */
export function ScanPanel({ listingId, current, hasPhoto, onChanged }: { listingId: string; current: VisualMatchData | null; hasPhoto: boolean; onChanged: () => void }) {
  const act = useAction();
  return (
    <section className="grid gap-4">
      <h3 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Scan foto kain</h3>
      <p className="text-base">Sistem membaca foto pertama: teknik, motif, dan warna. Lalu sistem memeriksa apakah tekniknya sesuai katalog tradisi yang Anda pilih, dan apakah fotonya mirip foto referensi yang disetujui kurator. Sistem tidak menebak asal kain; kurator Tenara yang memverifikasi.</p>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <button className="btn w-fit" disabled={act.busy || !hasPhoto} onClick={async () => { const r = await act.run(() => api("/vision/analyze", { body: { listing_id: listingId } })); if (r) onChanged(); }}>
        {act.busy ? "Menganalisis foto…" : current ? "Scan ulang" : "Scan foto"}
      </button>
      {!hasPhoto && <p className="text-base text-muted">Tambahkan foto kain dulu.</p>}
      {current && <div className="bg-surface p-5"><VisualMatch data={current} /></div>}
    </section>
  );
}
