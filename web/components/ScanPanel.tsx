"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Entry } from "@/lib/types";
import { Field, Notice, useAction, useLoad } from "./ui";
import { VisualMatch, type VisualMatchData } from "./VisualMatch";

/** Merchant-side: run the fabric scan, read the evidence, then confirm, reject or correct it. */
export function ScanPanel({ listingId, current, hasPhoto, onChanged }: { listingId: string; current: VisualMatchData | null; hasPhoto: boolean; onChanged: () => void }) {
  const act = useAction();
  const entries = useLoad(() => api<{ items: Entry[] }>("/gallery?limit=100"), "entries");
  const [claim, setClaim] = useState("");
  const [correctTo, setCorrectTo] = useState("");
  const s = current?.suggestion;
  const suggestedClaim = s?.verdict === "match" ? [s.tradition, s.region].filter(Boolean).join(", ") : "";
  const review = async (decision: "confirm" | "reject" | "correct") => {
    const body: Record<string, unknown> = { decision };
    if (decision === "correct") body.entry_id = correctTo;
    const text = claim || (decision === "confirm" ? suggestedClaim : "");
    if (text && decision !== "reject") body.merchant_claimed_origin = text;
    const r = await act.run(() => api(`/listings/${listingId}/motif-review`, { method: "PATCH", body }));
    if (r) { setClaim(""); onChanged(); }
  };
  return (
    <section className="grid gap-4">
      <h3 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Scan foto kain</h3>
      <p className="text-base">Sistem membaca foto pertama, mencocokkannya dengan katalog tenun Nusantara yang disetujui kurator, lalu menyarankan tradisi dan daerah beserta sumbernya. Anda yang memutuskan; kurator Tenara yang memverifikasi.</p>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <button className="btn w-fit" disabled={act.busy || !hasPhoto} onClick={async () => { const r = await act.run(() => api("/vision/analyze", { body: { listing_id: listingId } })); if (r) onChanged(); }}>
        {act.busy ? "Menganalisis foto…" : current ? "Scan ulang" : "Scan foto"}
      </button>
      {!hasPhoto && <p className="text-base text-muted">Tambahkan foto kain dulu.</p>}
      {current && (
        <div className="grid gap-5 bg-surface p-5">
          <VisualMatch data={current} />
          {current.needs_merchant_review ? (
            <div className="grid gap-4">
              <Field label="Klaim asal menurut Anda (opsional)" hint="Ditampilkan sebagai klaim penjual, terpisah dari verifikasi kurator.">
                <input className="field" value={claim} placeholder={suggestedClaim || "Misalnya: Sumba Timur, NTT"} onChange={(e) => setClaim(e.target.value)} />
              </Field>
              <div className="flex flex-wrap gap-3">
                <button className="btn" disabled={act.busy} onClick={() => review("confirm")}>Saran ini sesuai</button>
                <button className="btn btn-quiet" disabled={act.busy} onClick={() => review("reject")}>Tidak sesuai</button>
              </div>
              <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
                <Field label="Atau koreksi ke entri Gallery">
                  <select className="field" value={correctTo} onChange={(e) => setCorrectTo(e.target.value)}>
                    <option value="">Pilih entri…</option>
                    {entries.data?.items.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
                  </select>
                </Field>
                <button className="btn btn-quiet" disabled={act.busy || !correctTo} onClick={() => review("correct")}>Koreksi</button>
              </div>
            </div>
          ) : (
            <p className="text-base">Sudah Anda tinjau: {{ confirm: "dikonfirmasi", reject: "ditolak", correct: "dikoreksi" }[current.review?.decision ?? ""] ?? "-"}.</p>
          )}
        </div>
      )}
    </section>
  );
}
