"use client";

import { useState } from "react";
import { api, fileUrl } from "@/lib/api";
import type { GalleryVariant } from "@/lib/variants";
import { Field, Notice, useAction, useLoad } from "@/components/ui";
import { Upload } from "@/components/Upload";

function VariantEditor({ variant, onChanged }: { variant: GalleryVariant; onChanged: () => void }) {
  const [name, setName] = useState(variant.name);
  const [description, setDescription] = useState(variant.description);
  const [caption, setCaption] = useState("");
  const [credit, setCredit] = useState("");
  const [license, setLicense] = useState("");
  const act = useAction();
  return <div className="grid gap-3 bg-surface p-5">
    <h3 className="text-xl font-medium">{variant.name}</h3>
    {act.error && <Notice tone="error">{act.error}</Notice>}
    <details><summary className="cursor-pointer underline">Ubah varian</summary><div className="mt-3 grid gap-3"><Field label="Nama motif"><input className="field" value={name} onChange={(event) => setName(event.target.value)} /></Field><Field label="Keterangan"><textarea className="field" value={description} onChange={(event) => setDescription(event.target.value)} /></Field><button className="btn w-fit" disabled={act.busy || !name.trim()} onClick={async () => { const result = await act.run(() => api(`/admin/gallery/variants/${variant.id}`, { method: "PATCH", body: { name, description } })); if (result) onChanged(); }}>Simpan perubahan</button></div></details>
    <div className="flex flex-wrap gap-3">{variant.images.map((image) => <figure key={image.url}><img src={fileUrl(image.url)} alt={image.caption ?? variant.name} className="h-28 w-28 object-cover" /><figcaption className="max-w-28 text-sm">{[image.caption, image.credit, image.license].filter(Boolean).join(" · ")}</figcaption></figure>)}</div>
    <button className="link w-fit text-sm text-danger" disabled={act.busy} onClick={async () => { if (!window.confirm(`Hapus varian ${variant.name}? Listing yang masih memakai varian ini harus dipindahkan dahulu.`)) return; const result = await act.run(() => api(`/admin/gallery/variants/${variant.id}`, { method: "DELETE" })); if (result) onChanged(); }}>Hapus varian</button>
    <details><summary className="cursor-pointer underline">Tambah gambar referensi</summary><div className="mt-3 grid gap-3"><Field label="Keterangan"><input className="field" value={caption} onChange={(event) => setCaption(event.target.value)} /></Field><Field label="Kredit"><input className="field" value={credit} onChange={(event) => setCredit(event.target.value)} /></Field><Field label="Lisensi"><input className="field" value={license} onChange={(event) => setLicense(event.target.value)} /></Field><Upload kind="reference_image" label={`Pilih gambar ${variant.name}`} accept="image/jpeg,image/png,image/webp" onUploaded={async (file) => { const result = await act.run(() => api(`/admin/gallery/variants/${variant.id}/images`, { body: { file_id: file.id, caption: caption || variant.name, credit: credit || null, license: license || null } })); if (result) { setCaption(""); setCredit(""); setLicense(""); onChanged(); } }} /></div></details>
  </div>;
}

export function VariantManager({ entryId }: { entryId: string }) {
  const variants = useLoad(() => api<GalleryVariant[]>(`/admin/gallery/${entryId}/variants`), entryId);
  const act = useAction();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  return <section className="grid gap-4">
    <h2 className="t-head text-3xl">Varian motif</h2>
    <p>Gambar ini adalah referensi motif; penjual tetap mengunggah foto barangnya sendiri.</p>
    {variants.error && <Notice tone="error">{variants.error}</Notice>}
    {act.error && <Notice tone="error">{act.error}</Notice>}
    <Field label="Nama motif"><input className="field" value={name} onChange={(e) => setName(e.target.value)} /></Field>
    <Field label="Keterangan"><textarea className="field" value={description} onChange={(e) => setDescription(e.target.value)} /></Field>
    <button className="btn w-fit" disabled={act.busy || !name.trim()} onClick={async () => {
      const result = await act.run(() => api(`/admin/gallery/${entryId}/variants`, { body: { name, description } }));
      if (result) { setName(""); setDescription(""); variants.reload(); }
    }}>Tambah varian</button>
    {variants.data?.map((v) => <VariantEditor key={v.id} variant={v} onChanged={variants.reload} />)}
  </section>;
}
