"use client";

import { useId, useState } from "react";
import { api } from "@/lib/api";
import { Notice, errText } from "./ui";

export type Uploaded = { id: string; kind: string; url: string; content_type: string };

/** Uploads one file to POST /files and reports it; the caller keeps the list. */
export function Upload({ kind, label, onUploaded, accept = "image/jpeg,image/png,image/webp,application/pdf" }: { kind: string; label: string; onUploaded: (f: Uploaded) => void; accept?: string }) {
  const [busy, setBusy] = useState(false);
  const id = useId();
  const [error, setError] = useState<string | null>(null);
  return (
    <div className="grid gap-2">
      <label className="text-base" htmlFor={id}>{label}</label>
      <input
        id={id}
        type="file"
        accept={accept}
        disabled={busy}
        className="field !py-3"
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          setBusy(true);
          setError(null);
          try {
            const form = new FormData();
            form.set("kind", kind);
            form.set("file", file);
            onUploaded(await api<Uploaded>("/files", { form }));
          } catch (err) {
            setError(errText(err));
          } finally {
            setBusy(false);
            e.target.value = "";
          }
        }}
      />
      {busy && <p className="t-small">Mengunggah…</p>}
      {error && <Notice tone="error">{error}</Notice>}
    </div>
  );
}
