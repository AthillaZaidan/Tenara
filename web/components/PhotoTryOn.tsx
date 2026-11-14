"use client";

import { useEffect, useState } from "react";
import { api, fileUrl, when } from "@/lib/api";
import { Notice, useAction, useLoad } from "@/components/ui";

type Photo = { id: string; consent_id: string; created_at: string; delete_after: string };
type Preview = { id: string; status: string; design_revision: number; url: string | null; label: string; warnings: string[] };

export function PhotoTryOn({ custId, revision, frontPhotoId }: { custId: string; revision: number; frontPhotoId?: string }) {
  const photos = useLoad(() => api<Photo[]>("/body-photos"), `${custId}-${frontPhotoId ?? ""}`);
  const act = useAction();
  const [photo, setPhoto] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [pollError, setPollError] = useState("");
  const pending = preview && ["queued", "processing"].includes(preview.status);
  useEffect(() => {
    if (!preview || !pending) return;
    let active = true;
    const timer = setTimeout(async () => {
      try { const next = await api<Preview>(`/previews/${preview.id}`); if (active) { setPollError(""); setPreview(next); } }
      catch { if (active) setPollError("Status belum dapat dimuat. Muat ulang halaman untuk mencoba lagi."); }
    }, 2500);
    return () => { active = false; clearTimeout(timer); };
  }, [preview, pending]);
  const photoId = photo || frontPhotoId || "";
  const selected = photos.data?.find((p) => p.id === photoId);
  const stale = preview && preview.design_revision !== revision;
  return <div className="grid gap-4">
    <h3 className="text-xl font-medium">Fit On dengan foto</h3>
    <p>Pilih foto depan yang telah diunggah saat pengukuran. Ilustrasi hanya terlihat oleh Anda dan bukan jaminan kecocokan.</p>
    <button className="link w-fit" onClick={photos.reload}>Muat ulang daftar foto</button>
    {photos.error && <Notice tone="error">{photos.error}</Notice>}
    <label className="grid gap-2">Foto badan<select className="field" value={selected ? photoId : ""} onChange={(e) => setPhoto(e.target.value)}>
      <option value="">Pilih foto depan…</option>{photos.data?.map((p) => <option key={p.id} value={p.id}>Diunggah {when(p.created_at)} · tersimpan sampai {when(p.delete_after)}</option>)}
    </select></label>
    {photos.data?.length === 0 && <p>Belum ada foto tersimpan. Unggah foto melalui bagian ukuran badan.</p>}
    {act.error && <Notice tone="error">{act.error}</Notice>}{pollError && <div className="grid gap-2"><Notice tone="error">{pollError}</Notice><button className="btn btn-quiet w-fit" onClick={async () => {
      if (!preview) return;
      const updated = await act.run(() => api<Preview>(`/previews/${preview.id}`));
      if (updated) { setPollError(""); setPreview(updated); }
    }}>Periksa status lagi</button></div>}
    <div className="flex flex-wrap gap-3"><button className="btn" disabled={!selected || act.busy || !!pending} onClick={async () => {
      const p = await act.run(() => api<Preview>(`/customizations/${custId}/photo-try-ons`, { body: { body_photo_id: selected!.id } }));
      if (p) { setPollError(""); setPreview(p); }
    }}>Buat Fit On</button>
    {selected && <button className="btn btn-quiet" disabled={act.busy} onClick={async () => {
      if (!window.confirm("Hapus foto ini dan ilustrasi Fit On yang menggunakannya? Ukuran yang sudah dibuat tetap tersimpan.")) return;
      const result = await act.run(() => api(`/body-photos/${selected.id}`, { method: "DELETE" }));
      if (result) { setPhoto(""); setPreview(null); photos.reload(); }
    }}>Hapus foto</button>}
    {selected && <button className="btn btn-quiet" disabled={act.busy} onClick={async () => {
      if (!window.confirm("Cabut izin dan hapus semua foto yang terkait dengan izin ini?")) return;
      const result = await act.run(() => api(`/photo-consents/${selected.consent_id}/revoke`, { method: "POST" }));
      if (result) { setPhoto(""); setPreview(null); photos.reload(); }
    }}>Cabut izin foto</button>}</div>
    {pending && <p role="status">Ilustrasi sedang dibuat…</p>}
    {stale && <Notice>Desain telah berubah. Buat ulang Fit On untuk revisi terbaru.</Notice>}
    {preview?.status === "failed" && <Notice tone="error">Fit On gagal dibuat. {preview.warnings.join(" ")}</Notice>}
    {!stale && preview?.url && <figure className="m-0 grid max-w-md gap-2"><img src={fileUrl(preview.url)} alt="Ilustrasi desain pada foto Anda" className="w-full" /><figcaption>{preview.label}</figcaption></figure>}
    {preview?.warnings.map((warning) => <p key={warning} className="text-muted">{warning}</p>)}
  </div>;
}
