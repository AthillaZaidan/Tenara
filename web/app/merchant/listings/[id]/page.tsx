"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ArrowUpRight, Check, ImagePlus, Layers, Package, Plus, Send, Tag } from "lucide-react";
import type { Listing } from "@/components/ListingCard";
import { ScanPanel } from "@/components/ScanPanel";
import { ListingStory } from "@/components/ListingStory";
import { Upload } from "@/components/Upload";
import type { VisualMatchData } from "@/components/VisualMatch";
import { Field, Notice, RequireAuth, useAction, useLoad } from "@/components/ui";
import { WorkspaceError, WorkspaceLoading, WorkspacePage, WorkspacePanel } from "@/components/PartnerWorkspace";
import { api, fileUrl, idr } from "@/lib/api";
import type { GalleryVariant } from "@/lib/variants";

type Full = Listing & { status: string; revision: number };
type Stock = { listing_id: string; units: { id: string; length_m: number | null; quantity: number }[] };

function Manage() {
  const { id } = useParams<{ id: string }>();
  const l = useLoad(() => api<Full>(`/merchant/listings/${id}`), id);
  const stock = useLoad(() => api<Stock[]>("/merchant/stock").then((all) => all.find((s) => s.listing_id === id) ?? null), id);
  const variants = useLoad(() => l.data ? api<GalleryVariant[]>(`/gallery/${l.data.entry_id}/variants`) : Promise.resolve([]), l.data?.entry_id ?? "");
  const act = useAction();
  const [len, setLen] = useState("");
  const [qty, setQty] = useState("1");
  const [price, setPrice] = useState("");
  if (l.loading) return <WorkspaceLoading>Memuat detail kain…</WorkspaceLoading>;
  if (l.error || !l.data) return <WorkspaceError message={l.error ?? "Kain tidak ditemukan."} retry={l.reload} />;
  const x = l.data;
  const meter = x.selling_unit === "meter";
  const refresh = () => { l.reload(); stock.reload(); };
  const go = async <T,>(fn: () => Promise<T>) => { const r = await act.run(fn); if (r !== undefined) refresh(); };
  return (
    <div className="workspace-stack">
      <div className="workspace-detail-hero workspace-listing-title"><span><Layers size={26} strokeWidth={1.3} /></span><div><span className={`badge ${x.status === "published" ? "published" : x.status === "draft" ? "draft" : "archived"}`}>{x.status === "published" ? "Terbit" : x.status === "draft" ? "Draf" : "Diarsipkan"}</span><h2>{x.title}</h2><p>{idr(x.price_idr)} / {meter ? "meter" : "potong"}{x.material ? ` · ${x.material}` : ""} · Revisi {x.revision}</p></div></div>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <div className="workspace-two-column"><div className="workspace-stack">
      <WorkspacePanel title="Foto kain" description="Tampilkan tekstur dan detail motif dari sudut terbaiknya." icon={ImagePlus}>
        {x.images.length ? <div className="workspace-photos">{x.images.map((im) => <figure key={im.id} className="grid gap-2"><img src={fileUrl(im.url)} alt={im.caption ?? x.title} className="aspect-square w-full object-cover" />{x.images.length > 1 && <button className="link w-fit text-sm text-danger" disabled={act.busy} onClick={async () => { if (!window.confirm("Lepaskan foto ini dari listing? File gambar tidak dihapus karena mungkin dipakai sebagai referensi lain.")) return; await go(() => api(`/listings/${id}/images/${im.id}`, { method: "DELETE" })); }}>Hapus foto</button>}</figure>)}</div> : <div className="workspace-photo-empty"><ImagePlus size={28} strokeWidth={1.2} /><p>Tambahkan foto pertama agar pembeli dapat mengenal kain Anda.</p></div>}
        <Upload kind="listing_photo" label="Tambah foto kain (JPG, PNG, atau WebP)" accept="image/jpeg,image/png,image/webp" onUploaded={(f) => go(() => api(`/listings/${id}/images`, { body: { file_id: f.id, caption: x.title } }))} />
      </WorkspacePanel>
      <WorkspacePanel title="Tradisi & motif" description="Hubungkan kain Anda dengan motif yang tepat di katalog." icon={Layers}>
        {variants.error && <Notice tone="error">{variants.error}</Notice>}
        <Field label="Varian motif" hint="Perubahan motif langsung disimpan pada penawaran kain ini."><select className="field" value={x.variant_id ?? ""} disabled={act.busy || variants.loading} onChange={(e) => { const variantId = e.target.value || null; void go(() => api(`/listings/${id}`, { method: "PATCH", body: { expected_revision: x.revision, variant_id: variantId } })); }}><option value="">Belum dipetakan</option>{variants.data?.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}</select></Field>
        <dl className="workspace-key-values"><div><dt>Bahan</dt><dd>{x.material || "Belum diisi"}</dd></div><div><dt>Ukuran</dt><dd>{meter ? `Lebar ${x.usable_width_cm ?? "—"} cm` : `${x.piece_length_cm ?? "—"} × ${x.piece_width_cm ?? "—"} cm`}</dd></div><div><dt>Asal pengiriman</dt><dd>{[x.city, x.province].filter(Boolean).join(", ") || "Belum diisi"}</dd></div></dl>
      </WorkspacePanel>
      <ScanPanel listingId={id} current={(x.origin.visual_match as VisualMatchData | null) ?? null} hasPhoto={x.images.length > 0} onChanged={refresh} />
      <ListingStory listingId={id} hasScan={!!x.origin.visual_match} />
      </div><aside className="workspace-stack">
      <WorkspacePanel title="Publikasi kain" description="Siapkan detail kain sebelum tampil di etalase." icon={Send}>
        <p>{x.status === "published" ? "Kain Anda sudah dapat ditemukan oleh pembeli di etalase Tenara." : "Lengkapi foto, harga, dan stok, lalu terbitkan saat Anda siap."}</p>
        {x.status !== "published" && <button className="btn" disabled={act.busy} onClick={() => go(() => api(`/listings/${id}/publish`, { method: "POST" }))}><Send size={14} />Terbitkan kain</button>}
        {x.status === "published" && <Link href={`/listings/${id}`} className="workspace-link">Lihat halaman publik<ArrowUpRight size={14} /></Link>}
        {x.status !== "archived" && <button className="btn btn-quiet" disabled={act.busy} onClick={() => go(() => api(`/listings/${id}/archive`, { method: "POST" }))}>Arsipkan</button>}
      </WorkspacePanel>
      <WorkspacePanel title="Stok tersedia" description={meter ? `Total ${x.stock.total_length_m ?? 0} m · potongan utuh terpanjang ${x.stock.longest_continuous_m ?? 0} m` : `${x.stock.available_pieces ?? x.stock.pieces} potong tersedia`} icon={Package}>
        {stock.error && <div className="grid gap-2"><Notice tone="error">{stock.error}</Notice><button className="workspace-link" onClick={stock.reload}>Muat ulang stok</button></div>}
        {stock.loading ? <p role="status">Memuat stok…</p> : <ul className="workspace-stock-list">{stock.data?.units.map((u) => <li key={u.id}><Package size={14} />{meter ? `${u.length_m} m` : "Potong"} × {u.quantity}</li>)}{!stock.data?.units.length && !stock.error && <li>Belum ada stok. Tambahkan potongan pertama Anda.</li>}</ul>}
        <form className="workspace-stock-form" onSubmit={async (e) => { e.preventDefault(); await go(() => api(`/listings/${id}/stock-units`, { body: { length_m: meter ? len : null, quantity: Number(qty) } })); }}>
          {meter && <Field label="Panjang (m)"><input className="field" type="number" min="0.01" step="any" required inputMode="decimal" value={len} onChange={(e) => setLen(e.target.value)} placeholder="Contoh: 5" /></Field>}
          <Field label="Jumlah"><input className="field" type="number" min="1" step="1" required inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value)} /></Field>
          <button className="btn btn-quiet" disabled={act.busy || (meter && !len)}><Plus size={14} />Tambah stok</button>
        </form>
      </WorkspacePanel>
      <WorkspacePanel title="Harga kain" description={`Harga saat ini ${idr(x.price_idr)} / ${meter ? "meter" : "potong"}.`} icon={Tag}>
        <form className="workspace-stack" onSubmit={async (e) => { e.preventDefault(); await go(() => api(`/listings/${id}`, { method: "PATCH", body: { expected_revision: x.revision, price_idr: Number(price) } }).then((r) => { setPrice(""); return r; })); }}>
          <Field label="Harga baru (Rp)"><input className="field" type="number" min="1" required inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="Masukkan harga baru" /></Field>
          <button className="btn btn-quiet justify-self-start" disabled={act.busy || !price}>Simpan harga</button>
        </form>
      </WorkspacePanel>
      <div className="workspace-guide"><Check size={22} /><h2>Siap menjadi busana?</h2><p>{x.custom_order_ready ? "Kain ini sudah siap digunakan pembeli untuk merancang baju custom." : `Lengkapi detail berikut agar kain dapat digunakan untuk baju custom: ${x.missing_for_custom.map((key) => ({ material: "bahan kain", usable_width_cm: "lebar pakai", piece_dimensions: "ukuran potongan" }[key] ?? key)).join(", ") || "detail kain"}.`}</p></div>
      </aside></div>
    </div>
  );
}

export default function ManageListingPage() {
  return (
    <WorkspacePage role="merchant" active="collection" title="Kelola kain" description="Rawat setiap detail, dari foto pertama hingga siap dipilih pembeli." back={{ href: "/merchant#koleksi", label: "Koleksi kain" }}>
      <RequireAuth role="merchant"><Manage /></RequireAuth>
    </WorkspacePage>
  );
}
