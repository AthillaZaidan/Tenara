"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import type { Listing } from "@/components/ListingCard";
import { Notice, useLoad } from "@/components/ui";
import { api, fileUrl, idr } from "@/lib/api";
import type { GalleryVariant } from "@/lib/variants";

export function VariantOffers({ slug, variants, listings, initialVariant }: { slug: string; variants: GalleryVariant[]; listings: Listing[]; initialVariant?: string }) {
  const [selected, setSelected] = useState(variants.some((v) => v.id === initialVariant) ? initialVariant! : "");
  const filtered = useLoad(async () => selected
    ? { variant: selected, ...await api<{ items: Listing[] }>(`/gallery/${encodeURIComponent(slug)}/listings?variant_id=${encodeURIComponent(selected)}`, { token: null }) }
    : { variant: "", items: listings }, selected);
  const items = selected ? filtered.data?.items ?? [] : listings;

  return <section className="fabric-offers" aria-labelledby="listings">
    <div className="fabric-offers-heading">
      <div><p className="fabric-offers-kicker">Kain pilihanmu</p><h2 id="listings">Pilihan Kain dari Penyedia</h2><p>Bandingkan bahan, ukuran, harga, dan ketersediaan dari setiap penyedia.</p></div>
    </div>
    {variants.length > 0 && <div className="fabric-offers-variants" aria-label="Pilihan motif">
      <button type="button" aria-pressed={!selected} onClick={() => setSelected("")}>Semua motif</button>
      {variants.map((v) => <button type="button" key={v.id} aria-pressed={selected === v.id} onClick={() => setSelected(v.id)}>{v.name}</button>)}
    </div>}
    {filtered.error && selected ? <Notice tone="error">{filtered.error}</Notice> : selected && filtered.data?.variant !== selected ? <p>Memuat penawaran…</p> : items.length === 0 ? <div className="fabric-offers-empty"><h3>Belum ada penawaran kain</h3><p>Penawaran untuk pilihan ini belum tersedia.</p></div> :
      <ul className="fabric-offers-grid">{items.map((l) => <li key={l.id}>
        <Link className="fabric-offer-card" href={`/listings/${l.id}`}>
          <div className="fabric-offer-image">{l.images[0] ? <img src={fileUrl(l.images[0].url)} alt={l.images[0].caption ?? `Foto kain ${l.title} dari penyedia`} loading="lazy" /> : <span>Foto kain belum tersedia</span>}<span className="fabric-offer-photo-label">{l.images[0] ? "Foto dari penyedia" : "Menunggu foto penyedia"}</span></div>
          <div className="fabric-offer-info"><p className="fabric-offer-merchant">{[l.merchant?.shop_name, l.city].filter(Boolean).join(" · ")}</p><h3>{l.title}</h3><p>{[l.material, l.selling_unit === "meter" ? (l.usable_width_cm ? `Lebar ${l.usable_width_cm} cm` : null) : (l.piece_length_cm && l.piece_width_cm ? `${l.piece_length_cm} × ${l.piece_width_cm} cm` : null)].filter(Boolean).join(" · ")}</p><div className="fabric-offer-bottom"><strong>{idr(l.price_idr)} <small>/ {l.selling_unit === "meter" ? "meter" : "potong"}</small></strong><ArrowUpRight size={18} aria-hidden="true" /></div><span className="fabric-offer-stock">{l.stock.in_stock ? "Tersedia" : "Stok habis"}</span></div>
        </Link>
      </li>)}</ul>}
  </section>;
}
