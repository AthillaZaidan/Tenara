"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import type { Listing } from "@/components/ListingCard";
import { ScanPanel } from "@/components/ScanPanel";
import { Upload } from "@/components/Upload";
import type { VisualMatchData } from "@/components/VisualMatch";
import { Field, Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, fileUrl, idr } from "@/lib/api";

type Full = Listing & { status: string; revision: number };
type Stock = { listing_id: string; units: { id: string; length_m: number | null; quantity: number }[] };

function Manage() {
  const { id } = useParams<{ id: string }>();
  const l = useLoad(() => api<Full>(`/merchant/listings/${id}`), id);
  const stock = useLoad(() => api<Stock[]>("/merchant/stock").then((all) => all.find((s) => s.listing_id === id) ?? null), id);
  const act = useAction();
  const [len, setLen] = useState("");
  const [qty, setQty] = useState("1");
  const [price, setPrice] = useState("");
  if (l.loading) return <p>Memuat…</p>;
  if (l.error || !l.data) return <Notice tone="error">{l.error ?? "Kain tidak ditemukan."}</Notice>;
  const x = l.data;
  const meter = x.selling_unit === "meter";
  const refresh = () => { l.reload(); stock.reload(); };
  const go = async <T,>(fn: () => Promise<T>) => { const r = await act.run(fn); if (r !== undefined) refresh(); };
  return (
    <div className="grid max-w-3xl gap-12">
      <div>
        <p className="text-base text-muted">{x.status === "published" ? "Terbit" : x.status === "draft" ? "Draf" : "Diarsipkan"} · {idr(x.price_idr)} per {meter ? "meter" : "potong"}</p>
        <h1 className="t-head" style={{ fontSize: "clamp(2rem, 1.3rem + 3.2vw, 3.5rem)" }}>{x.title}</h1>
      </div>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <section className="grid gap-4">
        <h3 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Foto</h3>
        <div className="grid gap-4 sm:grid-cols-3">{x.images.map((im) => <img key={im.url} src={fileUrl(im.url)} alt={im.caption ?? x.title} className="aspect-square w-full object-cover" />)}</div>
        <Upload kind="listing_photo" label="Tambah foto kain (JPG, PNG, atau WebP)" accept="image/jpeg,image/png,image/webp" onUploaded={(f) => go(() => api(`/listings/${id}/images`, { body: { file_id: f.id, caption: x.title } }))} />
      </section>
      <ScanPanel listingId={id} current={(x.origin.visual_match as VisualMatchData | null) ?? null} hasPhoto={x.images.length > 0} onChanged={refresh} />
      <section className="grid gap-4">
        <h3 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Stok</h3>
        <p className="text-base">{meter ? `Total ${x.stock.total_length_m ?? 0} m, potongan utuh terpanjang ${x.stock.longest_continuous_m ?? 0} m.` : `${x.stock.pieces} potong.`} Pembeli menahan satu potongan utuh selama pembayaran.</p>
        <ul className="grid list-none gap-1 p-0 text-base">{stock.data?.units.map((u) => <li key={u.id}>{meter ? `${u.length_m} m` : "Potong"} × {u.quantity}</li>)}</ul>
        <div className="grid gap-3 sm:grid-cols-[1fr_8rem_auto] sm:items-end">
          {meter && <Field label="Panjang potongan (m)"><input className="field" inputMode="decimal" value={len} onChange={(e) => setLen(e.target.value)} /></Field>}
          <Field label="Jumlah"><input className="field" inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value)} /></Field>
          <button className="btn" disabled={act.busy || (meter && !len)} onClick={() => go(() => api(`/listings/${id}/stock-units`, { body: { length_m: meter ? len : null, quantity: Number(qty) || 1 } }))}>Tambah stok</button>
        </div>
      </section>
      <section className="grid gap-4">
        <h3 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Harga</h3>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <Field label="Harga baru (Rp)"><input className="field" inputMode="numeric" value={price} onChange={(e) => setPrice(e.target.value.replace(/\D/g, ""))} /></Field>
          <button className="btn btn-quiet" disabled={act.busy || !price} onClick={() => go(() => api(`/listings/${id}`, { method: "PATCH", body: { expected_revision: x.revision, price_idr: Number(price) } }).then((r) => { setPrice(""); return r; }))}>Ubah harga</button>
        </div>
      </section>
      <div className="flex flex-wrap gap-3">
        {x.status !== "published" && <button className="btn" disabled={act.busy} onClick={() => go(() => api(`/listings/${id}/publish`, { method: "POST" }))}>Terbitkan</button>}
        {x.status !== "archived" && <button className="btn btn-quiet" disabled={act.busy} onClick={() => go(() => api(`/listings/${id}/archive`, { method: "POST" }))}>Arsipkan</button>}
        {x.status === "published" && <Link href={`/listings/${id}`} className="btn btn-quiet no-underline">Lihat halaman publik</Link>}
      </div>
      {!x.custom_order_ready && x.missing_for_custom.length > 0 && <p className="text-base text-muted">Belum bisa dipakai untuk baju custom. Lengkapi: {x.missing_for_custom.join(", ")}.</p>}
    </div>
  );
}

export default function ManageListingPage() {
  return (
    <Page>
      <p className="mb-2 mt-6 text-base"><Link href="/merchant" className="link">← Dasbor</Link></p>
      <RequireAuth role="merchant"><Manage /></RequireAuth>
    </Page>
  );
}
