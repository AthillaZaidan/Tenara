"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight, BookOpen, Check, Layers, Save, Tag, Truck } from "lucide-react";
import { Field, Notice, RequireAuth, useAction, useLoad } from "@/components/ui";
import { WorkspacePage, WorkspacePanel } from "@/components/PartnerWorkspace";
import { api } from "@/lib/api";
import type { Entry } from "@/lib/types";
import type { GalleryVariant } from "@/lib/variants";

function Form() {
  const router = useRouter();
  const entries = useLoad(() => api<{ items: Entry[] }>("/gallery?limit=100"), "e");
  const act = useAction();
  const [f, setF] = useState({ entry_id: "", variant_id: "", title: "", description: "", selling_unit: "meter", price_idr: "", min_quantity: "1", quantity_increment: "0.5", material: "", usable_width_cm: "", piece_length_cm: "", piece_width_cm: "", city: "", province: "", dispatch_days: "3", merchant_claimed_origin: "" });
  const variants = useLoad(async () => ({ entryId: f.entry_id, items: f.entry_id ? await api<GalleryVariant[]>(`/gallery/${f.entry_id}/variants`) : [] }), f.entry_id);
  const currentVariants = variants.data?.entryId === f.entry_id ? variants.data.items : [];
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const meter = f.selling_unit === "meter";
  const num = (v: string) => (v ? Number(v) : null);
  return (
    <form
      className="workspace-stack"
      onSubmit={async (e) => {
        e.preventDefault();
        const body = { entry_id: f.entry_id, variant_id: f.variant_id || null, title: f.title, description: f.description, selling_unit: f.selling_unit, price_idr: Number(f.price_idr), min_quantity: meter ? f.min_quantity : "1", quantity_increment: meter ? f.quantity_increment : "1", material: f.material || null, usable_width_cm: meter ? num(f.usable_width_cm) : null, piece_length_cm: meter ? null : num(f.piece_length_cm), piece_width_cm: meter ? null : num(f.piece_width_cm), city: f.city || null, province: f.province || null, dispatch_days: Number(f.dispatch_days), merchant_claimed_origin: f.merchant_claimed_origin || null };
        const l = await act.run(() => api<{ id: string }>("/listings", { body }));
        if (l) router.push(`/merchant/listings/${l.id}`);
      }}
    >
      <div className="workspace-two-column"><div className="workspace-stack">
      <WorkspacePanel title="Identitas & cerita kain" description="Perkenalkan kain Anda dan tradisi yang melatarinya." icon={Layers}>
      {entries.error && <div className="grid gap-3"><Notice tone="error">{entries.error}</Notice><button type="button" className="workspace-link" onClick={entries.reload}>Muat ulang tradisi</button></div>}
      <div className="workspace-form-grid">
      <Field label="Tradisi kain" hint="Tautkan kain Anda dengan satu tradisi di galeri.">
        <select className="field" required disabled={entries.loading} value={f.entry_id} onChange={(e) => setF({ ...f, entry_id: e.target.value, variant_id: "" })}>
          <option value="">{entries.loading ? "Memuat tradisi…" : "Pilih tradisi kain"}</option>
          {entries.data?.items.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
      </Field>
      {variants.error && <Notice tone="error">{variants.error}</Notice>}
      {f.entry_id && <Field label="Varian motif" hint="Pilih motif yang sesuai, atau biarkan belum dipetakan."><select className="field" value={f.variant_id} onChange={set("variant_id")} disabled={variants.data?.entryId !== f.entry_id}><option value="">Belum dipetakan</option>{currentVariants.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}</select></Field>}
      <div className="workspace-span-all"><Field label="Nama kain"><input className="field" required value={f.title} onChange={set("title")} placeholder="Contoh: Tenun ikat Sumba — motif kuda" /></Field></div>
      <div className="workspace-span-all"><Field label="Deskripsi"><textarea className="field" value={f.description} onChange={set("description")} placeholder="Ceritakan warna, tekstur, dan keunikan kain Anda…" /></Field></div>
      <Field label="Bahan"><input className="field" value={f.material} onChange={set("material")} placeholder="Katun, sutra, songket…" /></Field>
      <div className="workspace-span-all"><Field label="Cerita asal-usul kain" hint="Keterangan dari Anda ditampilkan terpisah dari verifikasi kurator."><textarea className="field" value={f.merchant_claimed_origin} onChange={set("merchant_claimed_origin")} placeholder="Dari mana kain ini berasal dan bagaimana kain ini dibuat?" /></Field></div>
      </div></WorkspacePanel>
      <WorkspacePanel title="Harga & ukuran" description="Informasi yang jelas membantu pembeli memilih dengan tepat." icon={Tag}>
      <div className="workspace-form-grid">
        <Field label="Dijual per"><select className="field" value={f.selling_unit} onChange={set("selling_unit")}><option value="meter">Meter</option><option value="piece">Potong utuh</option></select></Field>
        <Field label={`Harga per ${meter ? "meter" : "potong"} (Rp)`}><input className="field" type="number" min="1" required inputMode="numeric" value={f.price_idr} onChange={set("price_idr")} placeholder="Contoh: 250000" /></Field>
        {meter ? (<>
          <Field label="Lebar pakai (cm)" hint="Dipakai untuk menghitung kebutuhan kain."><input className="field" type="number" min="1" step="1" required inputMode="numeric" value={f.usable_width_cm} onChange={set("usable_width_cm")} /></Field>
          <Field label="Minimum pembelian (m)"><input className="field" type="number" min="0.01" step="0.01" required inputMode="decimal" value={f.min_quantity} onChange={set("min_quantity")} /></Field>
          <Field label="Kelipatan pembelian (m)"><input className="field" type="number" min="0.01" step="0.01" required inputMode="decimal" value={f.quantity_increment} onChange={set("quantity_increment")} /></Field>
        </>) : (<>
          <Field label="Panjang potong (cm)"><input className="field" type="number" min="1" step="1" required inputMode="numeric" value={f.piece_length_cm} onChange={set("piece_length_cm")} /></Field>
          <Field label="Lebar potong (cm)"><input className="field" type="number" min="1" step="1" required inputMode="numeric" value={f.piece_width_cm} onChange={set("piece_width_cm")} /></Field>
        </>)}
      </div></WorkspacePanel>
      <WorkspacePanel title="Asal pengiriman" description="Bantu pembeli memperkirakan perjalanan kain pilihannya." icon={Truck}>
      <div className="workspace-form-grid">
        <Field label="Kota asal kirim"><input className="field" value={f.city} onChange={set("city")} /></Field>
        <Field label="Provinsi asal kirim"><input className="field" value={f.province} onChange={set("province")} /></Field>
        <Field label="Siap dikirim dalam (hari)"><input className="field" type="number" min="0" max="60" required inputMode="numeric" value={f.dispatch_days} onChange={set("dispatch_days")} /></Field>
      </div></WorkspacePanel>
      </div><aside className="workspace-stack"><div className="workspace-guide"><BookOpen size={27} strokeWidth={1.2} /><h2>Setiap kain punya cerita.</h2><p>Mulai dari detail yang paling Anda kenal. Foto dan stok dapat ditambahkan setelah draf tersimpan.</p><ul><li><Check size={14} />Pilih tradisi dan motif yang paling sesuai.</li><li><Check size={14} />Tulis ukuran dan harga dengan jelas.</li><li><Check size={14} />Tinjau kembali sebelum kain diterbitkan.</li></ul><Link href="/merchant#koleksi">Lihat koleksi Anda<ArrowRight size={14} /></Link></div></aside></div>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <div className="workspace-form-actions"><p>Draf tersimpan untuk Anda lengkapi sebelum diterbitkan.</p><div><Link href="/merchant#koleksi" className="workspace-link">Kembali</Link><button className="btn" disabled={act.busy}><Save size={15} />{act.busy ? "Menyimpan…" : "Simpan sebagai draf"}</button></div></div>
    </form>
  );
}

export default function NewListingPage() {
  return (
    <WorkspacePage role="merchant" active="collection" title="Tambah kain" description="Perkenalkan sehelai karya baru kepada pemilik berikutnya." back={{ href: "/merchant#koleksi", label: "Koleksi kain" }}>
      <RequireAuth role="merchant"><Form /></RequireAuth>
    </WorkspacePage>
  );
}
