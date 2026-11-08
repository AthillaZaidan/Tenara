"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Field, Notice, useAction, useLoad } from "./ui";
import { ClaimCheckView, type ClaimCheck } from "./VisualMatch";

type ClaimInfo = { claim_check: ClaimCheck | null; entry: { id: string; name: string } | null };

/** Curator-only: record the verified origin. Shown on the listing page to admins, with the photo claim check. */
export function VerifyOrigin({ listingId, current }: { listingId: string; current: string | null }) {
  const { has } = useAuth();
  if (!has("admin")) return null;
  return <CuratorPanel listingId={listingId} current={current} />;
}

function CuratorPanel({ listingId, current }: { listingId: string; current: string | null }) {
  const router = useRouter();
  const act = useAction();
  const [text, setText] = useState(current ?? "");
  const [asReference, setAsReference] = useState(false);
  const info = useLoad(() => api<ClaimInfo>(`/admin/listings/${listingId}/claim-check`), listingId);
  const entryName = info.data?.entry?.name ?? "entri Gallery listing ini";
  const save = async () => {
    const r = await act.run(() => api(`/admin/listings/${listingId}/verify-origin`, { body: { text, add_as_reference: asReference } }));
    if (r) { setAsReference(false); router.refresh(); }
  };
  return (
    <div className="grid max-w-xl gap-3 bg-surface p-5">
      <h2 className="text-lg font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Verifikasi kurator</h2>
      {info.data?.claim_check ? <ClaimCheckView check={info.data.claim_check} /> : <p className="text-base text-muted">Penjual belum menjalankan scan foto.</p>}
      <Field label="Asal-usul yang terverifikasi" hint="Isi hanya setelah memeriksa sumber dan bertanya ke penjual atau pengrajin.">
        <input className="field" value={text} onChange={(e) => setText(e.target.value)} />
      </Field>
      <label className="flex items-start gap-3 text-base">
        <input type="checkbox" className="mt-1" checked={asReference} onChange={(e) => setAsReference(e.target.checked)} />
        <span>Foto listing ini memang {entryName}; jadikan foto referensi untuk cek klaim berikutnya. <span className="t-small block text-muted">Dipakai untuk mencocokkan saja, tidak ditampilkan ke pengguna lain.</span></span>
      </label>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <button className="btn w-fit" disabled={act.busy || !text.trim()} onClick={save}>Simpan verifikasi</button>
    </div>
  );
}
