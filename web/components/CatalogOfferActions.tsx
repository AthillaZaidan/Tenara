"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Listing } from "@/components/ListingCard";
import { idr } from "@/lib/api";

export function CatalogOfferActions({ listing, initialBuy = false, initialQuantity }: { listing: Listing; initialBuy?: boolean; initialQuantity?: string }) {
  const router = useRouter();
  const [mode, setMode] = useState<"fabric" | null>(initialBuy ? "fabric" : null);
  const [quantity, setQuantity] = useState(initialQuantity ?? String(listing.min_quantity));
  const meter = listing.selling_unit === "meter";
  const unit = meter ? "meter" : "potong";
  const qty = Number(quantity);
  const increment = Number(listing.quantity_increment);
  const minimum = Number(listing.min_quantity);
  const validQuantity = Number.isFinite(qty) && qty >= minimum && increment > 0 && Math.abs((qty - minimum) / increment - Math.round((qty - minimum) / increment)) < 1e-8;

  return <div className="catalog-purchase">
    <div className="catalog-purchase-actions">
      <Link className={`ecommerce-action catalog-studio-action${!listing.stock.in_stock || !listing.custom_order_ready ? " is-disabled" : ""}`} href={listing.stock.in_stock && listing.custom_order_ready ? `/studio/${listing.id}` : "#listings"} aria-disabled={!listing.stock.in_stock || !listing.custom_order_ready} onClick={(event) => { if (!listing.stock.in_stock || !listing.custom_order_ready) event.preventDefault(); }}>Buat produk di Studio</Link>
      <button type="button" className="catalog-buy-toggle" aria-expanded={mode === "fabric"} aria-controls={`catalog-buy-${listing.id}`} disabled={!listing.stock.in_stock} onClick={() => setMode(mode === "fabric" ? null : "fabric")}>Beli langsung</button>
    </div>
    {!listing.custom_order_ready && <p className="catalog-purchase-hint">Data kain belum lengkap untuk dibuat menjadi produk.</p>}
    {!listing.stock.in_stock && <p className="catalog-purchase-hint">Stok kain ini habis.</p>}
    <div id={`catalog-buy-${listing.id}`} className={`catalog-buy-collapse${mode === "fabric" ? " is-open" : ""}`} aria-hidden={mode !== "fabric"} inert={mode !== "fabric"}><div className="catalog-buy-content"><div className="catalog-purchase-form">
      <div className="catalog-quantity-heading"><label htmlFor="catalog-quantity">Jumlah kain</label><span>{meter ? `Lebar ${listing.usable_width_cm ?? "—"} cm` : `${listing.piece_length_cm ?? "—"} × ${listing.piece_width_cm ?? "—"} cm / potong`}</span></div>
      <div className="catalog-quantity-input"><input id="catalog-quantity" type="number" min={minimum} step={increment} value={quantity} onChange={(event) => setQuantity(event.target.value)} /><span>{unit}</span></div>
      <p className="catalog-purchase-hint">Minimal {minimum} {unit}, kelipatan {increment} {unit}{meter && listing.stock.longest_continuous_m != null ? ` · Potongan utuh terpanjang ${listing.stock.longest_continuous_m} m` : ""}</p>
      {!validQuantity && <p className="catalog-purchase-error" role="status">Masukkan jumlah sesuai minimum dan kelipatan yang tersedia.</p>}
      <div className="catalog-purchase-subtotal"><span>Total harga kain</span><strong>{idr(validQuantity ? qty * Number(listing.price_idr) : 0)}</strong></div>
      <button type="button" className="ecommerce-action catalog-checkout-button" disabled={!validQuantity || !listing.stock.in_stock} onClick={() => router.push(`/checkout/new?listing=${encodeURIComponent(listing.id)}&quantity=${encodeURIComponent(quantity)}`)}>Lanjut ke pembayaran</button>
      <p className="catalog-purchase-hint">Ongkos kirim dihitung pada langkah berikutnya.</p>
    </div></div></div>
  </div>;
}
