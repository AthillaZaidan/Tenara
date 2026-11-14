"use client";

import { api } from "@/lib/api";
import { Notice, useAction } from "./ui";
import { VisualMatch, type VisualMatchData } from "./VisualMatch";
import { ScanLine } from "lucide-react";
import { WorkspacePanel } from "./PartnerWorkspace";

/** Merchant-side: describe the fabric photo and check it against the listing's own Gallery entry (the claim). */
export function ScanPanel({ listingId, current, hasPhoto, onChanged }: { listingId: string; current: VisualMatchData | null; hasPhoto: boolean; onChanged: () => void }) {
  const act = useAction();
  return (
    <WorkspacePanel title="Kenali kain dari foto" description="Baca teknik, motif, dan warna untuk melengkapi informasi kain." icon={ScanLine}>
      <p>Foto pertama dibandingkan dengan tradisi dan referensi yang disetujui kurator. Hasil scan membantu menjelaskan kain; verifikasi asal-usul tetap dilakukan oleh kurator Tenara.</p>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <button className="btn w-fit" disabled={act.busy || !hasPhoto} onClick={async () => { const r = await act.run(() => api("/vision/analyze", { body: { listing_id: listingId } })); if (r) onChanged(); }}>
        {act.busy ? "Menganalisis foto…" : current ? "Scan ulang" : "Scan foto"}
      </button>
      {!hasPhoto && <p className="text-base text-muted">Tambahkan foto kain dulu.</p>}
      {current && <div className="bg-surface p-5"><VisualMatch data={current} /></div>}
    </WorkspacePanel>
  );
}
