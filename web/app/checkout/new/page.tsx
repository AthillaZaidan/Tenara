"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { ArrowLeft, ArrowRight, Check, MapPin, Plus } from "lucide-react";
import { AddressForm } from "@/components/AddressForm";
import { Footer } from "@/components/Footer";
import { Nav } from "@/components/Nav";
import type { Listing } from "@/components/ListingCard";
import { Notice, useAction, useLoad } from "@/components/ui";
import { ApiError, api, fileUrl, idr, intentKey } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Address = { id: string; label: string; recipient_name: string; phone?: string; line1: string; city: string; province: string; postal_code?: string | null };
type CheckoutEstimate = { unit_price_idr: number; subtotal_idr: number; shipping_idr: number; service_fee_idr: number; total_idr: number };
const isUuid = (value: string | undefined) => !!value && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);

export default function NewCheckoutPage() {
  return <><Nav /><main className="checkout-prepare-surface"><Suspense fallback={<p className="checkout-loading">Memuat pesanan…</p>}><NewCheckout /></Suspense></main><Footer /></>;
}

function NewCheckout() {
  const search = useSearchParams();
  const listingId = search.get("listing") ?? "";
  const [quantity, setQuantity] = useState(search.get("quantity") ?? "");
  const router = useRouter();
  const { me, ready } = useAuth();
  const [addressId, setAddressId] = useState("");
  const listing = useLoad(() => listingId ? api<Listing>(`/listings/${encodeURIComponent(listingId)}`, { token: null }) : Promise.reject(new Error("Kain tidak ditemukan.")), listingId);
  const addresses = useLoad(() => me ? api<Address[]>("/addresses") : Promise.resolve([]), me?.id ?? "anon");
  const action = useAction();
  const validAddresses = (addresses.data ?? []).filter((address) => isUuid(address.id));
  const chosen = isUuid(addressId) && validAddresses.some((address) => address.id === addressId)
    ? addressId
    : validAddresses[0]?.id ?? "";
  const value = Number(quantity);
  const minimum = Number(listing.data?.min_quantity);
  const increment = Number(listing.data?.quantity_increment);
  const maxQuantity = listing.data?.selling_unit === "meter"
    ? Number(listing.data.stock.longest_continuous_m ?? 0)
    : Number(listing.data?.stock.available_pieces ?? listing.data?.stock.pieces ?? 0);
  const validQuantity = !!quantity && Number.isFinite(value) && value >= minimum && value <= maxQuantity && increment > 0 && Math.abs((value - minimum) / increment - Math.round((value - minimum) / increment)) < 1e-8;
  const next = `/checkout/new?listing=${encodeURIComponent(listingId)}&quantity=${encodeURIComponent(quantity)}`;
  const unit = listing.data?.selling_unit === "meter" ? "meter" : "potong";
  const subtotal = Number.isFinite(value) && value > 0 && listing.data ? value * Number(listing.data.price_idr) : 0;
  const estimateKey = `${listingId}:${quantity}:${chosen}`;
  const estimate = useLoad<{ key: string; quote: CheckoutEstimate | null }>(async () => {
    if (!isUuid(listingId) || !isUuid(chosen) || !validQuantity || !listing.data?.stock.in_stock) return { key: estimateKey, quote: null };
    const params = new URLSearchParams({ listing_id: listingId, quantity, delivery_address_id: chosen });
    try {
      const quote = await api<CheckoutEstimate>(`/fabric-checkouts/estimate?${params.toString()}`);
      return { key: estimateKey, quote };
    } catch (error) {
      if (error instanceof ApiError && error.field === "checkout_id") {
        throw new Error("Server checkout belum memuat endpoint estimasi terbaru. Muat ulang API backend, lalu coba lagi.");
      }
      if (error instanceof ApiError && error.field === "delivery_address_id") {
        throw new Error("Alamat ini tidak dikenali. Pilih atau tambahkan ulang alamat pengiriman.");
      }
      throw error;
    }
  }, estimateKey);
  const currentQuote = estimate.data?.key === estimateKey ? estimate.data.quote : null;
  const estimateError = estimate.error && /valid uuid/i.test(estimate.error)
    ? "Alamat atau kain ini memiliki ID yang tidak valid. Pilih alamat lain atau buka kembali checkout dari halaman kain."
    : estimate.error;

  return <div className="checkout-page checkout-prepare">
    <Link className="checkout-prepare-back" href={listingId ? `/listings/${encodeURIComponent(listingId)}` : "/katalog"}><ArrowLeft size={16} aria-hidden="true" /> Kembali ke kain</Link>
    <header className="checkout-heading"><h1>Checkout</h1><p>Ke mana kain pilihanmu akan dikirim?</p></header>
    {listing.loading ? <p>Memuat pesanan…</p> : listing.error || !listing.data ? <Notice tone="error">{listing.error ?? "Kain tidak ditemukan."}</Notice> : <div className="checkout-layout">
      <div className="checkout-main">
        {!ready ? <p>Memuat akun…</p> : !me ? <section className="checkout-card"><h2>Masuk untuk melanjutkan</h2><p className="checkout-prepare-copy">Masuk untuk memilih alamat pengiriman dan melanjutkan pesanan.</p><Link className="btn" href={`/login?next=${encodeURIComponent(next)}`}>Masuk</Link></section> : <section className="checkout-card checkout-prepare-address">
          <div className="checkout-prepare-section-heading"><h2 id="delivery-address-title">Alamat pengiriman</h2><span>{validAddresses.length ? `${validAddresses.length} alamat tersimpan` : ""}</span></div>
          {addresses.loading ? <p>Memuat alamat…</p> : addresses.error ? <Notice tone="error">{addresses.error}</Notice> : validAddresses.length ? <fieldset className="checkout-address-options" aria-labelledby="delivery-address-title" disabled={action.busy}><legend className="catalog-sr-only">Pilih alamat pengiriman</legend>{validAddresses.map((address) => <label className={`checkout-address-option${chosen === address.id ? " is-selected" : ""}`} key={address.id}>
            <input type="radio" name="delivery-address" value={address.id} checked={chosen === address.id} onChange={() => setAddressId(address.id)} />
            <span className="checkout-address-option-copy"><span className="checkout-address-option-title"><strong>{address.label}</strong>{chosen === address.id && <span><Check size={13} aria-hidden="true" /> Dipilih</span>}</span><strong className="checkout-address-recipient">{address.recipient_name}</strong><span>{address.line1}</span><span>{[address.city, address.province, address.postal_code].filter(Boolean).join(", ")}</span>{address.phone && <span>{address.phone}</span>}</span>
          </label>)}</fieldset> : <div className="checkout-address-empty"><MapPin size={23} strokeWidth={1.5} aria-hidden="true" /><p>{addresses.data?.length ? "Alamat tersimpan perlu ditambahkan ulang sebelum dapat dipakai checkout." : "Belum ada alamat tersimpan. Tambahkan alamat untuk melanjutkan."}</p></div>}
          <div className="checkout-prepare-add-address"><Plus size={16} aria-hidden="true" /><AddressForm onCreated={(id) => { setAddressId(id); addresses.reload(); }} /></div>
        </section>}
      </div>
      <aside className="checkout-prepare-summary" aria-labelledby="prepare-summary-title">
        <h2 id="prepare-summary-title">Ringkasan pesanan</h2>
        <div className="checkout-prepare-item"><Link href={`/listings/${encodeURIComponent(listingId)}`} className="checkout-prepare-item-image">{listing.data.images[0] ? <img src={fileUrl(listing.data.images[0].url)} alt={listing.data.images[0].caption ?? listing.data.title} /> : <span>Tenara</span>}</Link><div><h3>{listing.data.title}</h3><p>{[listing.data.material, listing.data.usable_width_cm ? `Lebar ${listing.data.usable_width_cm} cm` : null].filter(Boolean).join(" · ")}</p><p>{idr(listing.data.price_idr)} / {unit}</p></div></div>
        <label className="checkout-prepare-quantity" htmlFor="checkout-prepare-quantity"><span>Jumlah kain</span><span className="checkout-prepare-quantity-control"><input id="checkout-prepare-quantity" type="number" inputMode="decimal" min={minimum} max={maxQuantity || undefined} step={increment} value={quantity} onChange={(event) => setQuantity(event.target.value)} aria-invalid={!validQuantity} aria-describedby="checkout-prepare-quantity-hint" /><span>{unit}</span></span></label>
        <p className="checkout-prepare-quantity-hint" id="checkout-prepare-quantity-hint">Minimum {minimum} {unit} · kelipatan {increment}{Number.isFinite(maxQuantity) && maxQuantity > 0 ? ` · maksimum ${maxQuantity} ${unit}` : ""}</p>
        {!listing.data.stock.in_stock ? <Notice tone="error">Stok kain sedang habis.</Notice> : !validQuantity && quantity && <p className="checkout-prepare-validation" role="status">Masukkan jumlah antara {minimum} dan {maxQuantity} {unit}, sesuai kelipatannya.</p>}
        <dl className="checkout-prepare-totals"><div><dt>Subtotal kain</dt><dd>{idr(subtotal)}</dd></div><div><dt>Ongkos kirim</dt><dd>{currentQuote ? idr(currentQuote.shipping_idr) : estimate.error ? "Periksa alamat" : estimate.data?.key === estimateKey ? "Pilih alamat" : "Menghitung…"}</dd></div>{!!currentQuote?.service_fee_idr && <div><dt>Biaya layanan</dt><dd>{idr(currentQuote.service_fee_idr)}</dd></div>}</dl>
        <div className="checkout-prepare-subtotal"><span>Total pesanan</span><strong>{currentQuote ? idr(currentQuote.total_idr) : "—"}</strong></div>
        <p className="checkout-prepare-shipping-note">Ongkos kirim dan total dihitung berdasarkan alamat pilihanmu.</p>
        {(action.error || estimateError) && <Notice tone="error">{action.error ?? estimateError}</Notice>}
        <button type="button" className="checkout-button" disabled={action.busy || !chosen || !me || !ready || !validQuantity || !listing.data.stock.in_stock || addresses.loading || !!addresses.error || !currentQuote || estimate.data?.key !== estimateKey} onClick={async () => {
            const checkout = await action.run(() => api<{ id: string }>("/fabric-checkouts/continue", { body: { listing_id: listingId, quantity, delivery_address_id: chosen }, idempotencyKey: intentKey(`checkout.continue.${listingId}.${quantity}.${chosen}`) }));
            if (checkout) router.push(`/checkout/${checkout.id}`);
          }}>{action.busy ? "Menyiapkan pembayaran…" : "Lanjut ke pembayaran"}<ArrowRight size={16} aria-hidden="true" /></button>
      </aside>
    </div>}
  </div>;
}
