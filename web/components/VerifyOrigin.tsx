"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Field, Notice, useAction } from "./ui";

/** Curator-only: record the verified origin. Shown on the listing page to admins. */
export function VerifyOrigin({ listingId, current }: { listingId: string; current: string | null }) {
  const { has } = useAuth();
  const router = useRouter();
  const act = useAction();
  const [text, setText] = useState(current ?? "");
  if (!has("admin")) return null;
  return (
    <div className="grid max-w-xl gap-3 bg-surface p-5">
      <h2 className="text-lg font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Verifikasi kurator</h2>
      <Field label="Asal-usul yang terverifikasi" hint="Isi hanya setelah memeriksa sumber dan bertanya ke penjual atau pengrajin.">
        <input className="field" value={text} onChange={(e) => setText(e.target.value)} />
      </Field>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <button className="btn w-fit" disabled={act.busy || !text.trim()} onClick={async () => { const r = await act.run(() => api(`/admin/listings/${listingId}/verify-origin`, { body: { text } })); if (r) router.refresh(); }}>Simpan verifikasi</button>
    </div>
  );
}
