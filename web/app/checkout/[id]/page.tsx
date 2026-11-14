"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Check, Clock3, MapPin, PackageCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Footer } from "@/components/Footer";
import { Nav } from "@/components/Nav";
import { Field, Notice, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, fileUrl, idr, intentKey, when } from "@/lib/api";
import { AddressForm } from "@/components/AddressForm";

type Checkout = {
  id: string;
  status: string;
  listing_id: string;
  listing_title: string;
  quantity: number;
  selling_unit: string;
  unit_price_idr: number;
  subtotal_idr: number;
  shipping_idr: number;
  service_fee_idr: number;
  total_idr: number;
  expires_at: string | null;
  address: { id: string; label: string; recipient_name: string; phone: string; line1: string; city: string; province: string; postal_code?: string | null };
  payment: { id: string; status: string } | null;
};

type DeliveryAddress = { id: string; label: string; recipient_name: string; phone: string; line1: string; city: string; province: string; postal_code: string | null };

type ListingPreview = {
  title: string;
  material: string | null;
  usable_width_cm: number | null;
  images: { id: string; url: string; caption: string | null }[];
};

function useCountdown(iso: string | null) {
  const [left, setLeft] = useState<number | null>(null);
  useEffect(() => {
    if (!iso) return;
    const tick = () => setLeft(Math.max(0, Math.floor((new Date(iso).getTime() - Date.now()) / 1000)));
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [iso]);
  return left;
}

function CheckoutProduct({ checkout }: { checkout: Checkout }) {
  const { data: listing } = useLoad(
    () => api<ListingPreview>(`/listings/${checkout.listing_id}`),
    checkout.listing_id,
  );
  const image = listing?.images[0];
  const unit = checkout.selling_unit === "meter" ? "meter" : "potong";
  const quantity = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 2 }).format(checkout.quantity);

  return (
    <section className="checkout-card checkout-product" aria-labelledby="checkout-product-title">
      <div className="checkout-card-heading">
        <div>
          <h2 id="checkout-product-title">Kain pilihanmu</h2>
        </div>
      </div>
      <div className="checkout-product-row">
        <Link href={`/listings/${checkout.listing_id}`} className="checkout-product-image" aria-label={`Lihat detail ${listing?.title ?? checkout.listing_title}`}>
          {image ? <img src={fileUrl(image.url)} alt={image.caption ?? listing?.title ?? checkout.listing_title} /> : <span>Tenara</span>}
        </Link>
        <div className="checkout-product-info">
          <h3>{listing?.title ?? checkout.listing_title}</h3>
          <p>{listing?.material ?? "Kain pilihan"}{listing?.usable_width_cm ? ` · Lebar ${listing.usable_width_cm} cm` : ""}</p>
          <p className="checkout-product-quantity">{quantity} {unit} <span>×</span> {idr(checkout.unit_price_idr)} / {unit}</p>
          <Link href={`/listings/${checkout.listing_id}`} className="checkout-detail-link">
            Lihat detail katalog <ArrowRight size={14} aria-hidden="true" />
          </Link>
        </div>
        <strong className="checkout-product-subtotal">{idr(checkout.subtotal_idr)}</strong>
      </div>
    </section>
  );
}

function CheckoutView() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: co, error, reload, loading } = useLoad(() => api<Checkout>(`/fabric-checkouts/${id}`), id);
  const addresses = useLoad(() => api<DeliveryAddress[]>("/addresses"), id);
  const act = useAction();
  const addressAct = useAction();
  const [editingAddress, setEditingAddress] = useState(false);
  const [selectedAddressId, setSelectedAddressId] = useState("");
  const left = useCountdown(co?.expires_at ?? null);

  if (loading) return <p className="checkout-loading">Memuat pesanan…</p>;
  if (error || !co) return <div className="checkout-error"><Notice tone="error">{error ?? "Checkout tidak ditemukan."}</Notice></div>;

  const expired = left === 0 || co.status === "expired";
  const rows: [string, number][] = [
    ["Subtotal kain", co.subtotal_idr],
    ["Ongkos kirim (simulasi)", co.shipping_idr],
    ...(co.service_fee_idr ? ([ ["Biaya layanan", co.service_fee_idr] ] as [string, number][]) : []),
  ];

  return (
    <section className="checkout-page">
      <nav className="checkout-progress" aria-label="Tahap checkout">
        <Link href={`/listings/${co.listing_id}`} className="checkout-progress-back" aria-label="Kembali ke detail kain">
          <ArrowLeft size={17} aria-hidden="true" />
        </Link>
        <ol>
          <li className="checkout-progress-done"><Check size={14} aria-hidden="true" /> Detail pesanan</li>
          <li className="checkout-progress-current"><i aria-hidden="true" /> Pembayaran</li>
        </ol>
        <span className="checkout-progress-count">LANGKAH 2 DARI 2</span>
      </nav>

      <header className="checkout-heading">
        <p className="checkout-overline">{co.status === "review" ? "Hampir selesai" : co.status === "payment_pending" ? "Pesanan siap" : "Status pesanan"}</p>
        <h1>{co.status === "review" ? "Periksa pesananmu" : co.status === "payment_pending" ? "Selesaikan pembayaran" : "Pesananmu"}</h1>
        <p>{co.status === "review" ? "Detail kain, jumlah, dan alamat sudah tersimpan. Pastikan semuanya benar sebelum melanjutkan." : co.status === "payment_pending" ? "Pesanan dan alamat pengiriman sudah dikonfirmasi. Selesaikan pembayaran sebelum waktu penahanan stok berakhir." : "Berikut detail terbaru pesanan kainmu."}</p>
      </header>

      <div className="checkout-layout">
        <div className="checkout-main">
          <CheckoutProduct checkout={co} />

          <section className="checkout-card checkout-address" aria-labelledby="checkout-address-title">
            <div className="checkout-card-heading checkout-address-heading">
              <div>
                <h2 id="checkout-address-title">Alamat pengiriman</h2>
              </div>
              {co.status === "review" && <button type="button" className="checkout-edit-address" aria-expanded={editingAddress} aria-controls="checkout-address-editor" onClick={() => { setEditingAddress((open) => !open); setSelectedAddressId(co.address.id); }}>{editingAddress ? "Tutup" : "Ubah alamat"}</button>}
            </div>
            <div className="checkout-address-details">
              <span className="checkout-address-icon"><MapPin size={18} aria-hidden="true" /></span>
              <div>
                {co.address.label && <p className="checkout-address-label">{co.address.label}</p>}
                <strong>{co.address.recipient_name}</strong>
                <p>{co.address.line1}</p>
                <p>{[co.address.city, co.address.province].filter(Boolean).join(", ")}</p>
                {co.address.postal_code && <p>{co.address.postal_code}</p>}
              </div>
              <span className="checkout-confirmed"><Check size={13} aria-hidden="true" /> Terkonfirmasi</span>
            </div>
            {editingAddress && co.status === "review" && <div className="checkout-address-editor" id="checkout-address-editor">
              {addresses.error && <Notice tone="error">{addresses.error}</Notice>}
              <Field label="Pilih alamat tersimpan">
                <select className="field" value={selectedAddressId || co.address.id} onChange={(event) => setSelectedAddressId(event.target.value)}>
                  {!addresses.data?.some((address) => address.id === co.address.id) && <option value={co.address.id}>{co.address.label}: {co.address.recipient_name}, {co.address.city}</option>}
                  {addresses.data?.map((address) => <option key={address.id} value={address.id}>{address.label}: {address.recipient_name}, {address.line1}, {address.city}</option>)}
                </select>
              </Field>
              <AddressForm onCreated={(addressId) => { setSelectedAddressId(addressId); addresses.reload(); }} />
              {addressAct.error && <Notice tone="error">{addressAct.error}</Notice>}
              <button type="button" className="checkout-button checkout-save-address" disabled={addressAct.busy || !(selectedAddressId || co.address.id)} onClick={async () => {
                const result = await addressAct.run(() => api(`/fabric-checkouts/${id}/address`, { method: "PATCH", body: { delivery_address_id: selectedAddressId || co.address.id } }));
                if (result) { setEditingAddress(false); await addresses.reload(); reload(); }
              }}>{addressAct.busy ? "Menyimpan…" : "Gunakan alamat ini"}</button>
            </div>}
          </section>

          {co.status !== "review" && <section className="checkout-payment" aria-label="Status pembayaran">
            {co.status === "payment_pending" && co.payment && (
              <div className="checkout-pending-panel">
                <div className="checkout-pending-title"><Clock3 size={18} aria-hidden="true" /><strong>Simulasi pembayaran siap</strong></div>
                <p>{expired ? "Waktu pembayaran habis; stok telah dilepas." : <>Selesaikan sebelum {when(co.expires_at)}. Sisa waktu <strong>{Math.floor((left ?? 0) / 60)}:{String((left ?? 0) % 60).padStart(2, "0")}</strong>.</>}</p>
                {act.error && <Notice tone="error">{act.error}</Notice>}
                <div className="checkout-payment-actions">
                  <button className="checkout-button" disabled={act.busy || expired} onClick={async () => {
                    const result = await act.run(() => api<{ order: { id: string } }>(`/demo-payments/${co.payment!.id}/complete`, {
                      body: { outcome: "succeeded" },
                      idempotencyKey: intentKey(`payment.${co.payment!.id}.succeeded`),
                    }));
                    if (result) router.push(`/orders/${result.order.id}`);
                  }}>
                    <PackageCheck size={17} aria-hidden="true" /> Simulasikan pembayaran berhasil
                  </button>
                  <button className="checkout-button-quiet" disabled={act.busy || expired} onClick={async () => {
                    const result = await act.run(() => api(`/demo-payments/${co.payment!.id}/complete`, {
                      body: { outcome: "failed" },
                      idempotencyKey: intentKey(`payment.${co.payment!.id}.failed`),
                    }));
                    if (result) reload();
                  }}>
                    Simulasikan pembayaran gagal
                  </button>
                </div>
              </div>
            )}

            {["expired", "failed", "cancelled"].includes(co.status) && (
              <div className="checkout-failed-panel" role="status">
                <p>Checkout ini {co.status === "expired" ? "kedaluwarsa" : "tidak berhasil"}. Pesanan belum dibayar.</p>
                <Link href={`/listings/${co.listing_id}`} className="checkout-detail-link">Kembali ke detail kain <ArrowRight size={14} aria-hidden="true" /></Link>
              </div>
            )}
          </section>}
        </div>

        <aside className="checkout-summary" aria-labelledby="checkout-summary-title">
          <h2 id="checkout-summary-title">Ringkasan pesanan</h2>
          <dl>
            {rows.map(([label, amount]) => (
              <div key={label}><dt>{label}</dt><dd>{idr(amount)}</dd></div>
            ))}
          </dl>
          <div className="checkout-total"><span>Total pembayaran</span><strong>{idr(co.total_idr)}</strong></div>

          {co.status === "review" && (
            <>
              {act.error && <Notice tone="error">{act.error}</Notice>}
              <button className="checkout-button" disabled={act.busy} onClick={async () => {
                const result = await act.run(() => api(`/fabric-checkouts/${id}/confirm`, {
                  body: { expected_total_idr: co.total_idr },
                  idempotencyKey: intentKey(`checkout.${id}.${co.total_idr}`),
                }));
                if (result) reload();
              }}>
                {act.busy ? "Memproses…" : "Lanjut ke pembayaran"}
                {!act.busy && <ArrowRight size={17} aria-hidden="true" />}
              </button>
            </>
          )}

          {co.status === "payment_pending" && <div className="checkout-summary-status"><Clock3 size={15} aria-hidden="true" /> Menunggu pembayaran</div>}
          {expired && <div className="checkout-summary-status checkout-summary-expired">Waktu pembayaran habis</div>}
        </aside>
      </div>
    </section>
  );
}

export default function CheckoutPage() {
  return (
    <>
      <Nav />
      <main className="catalog-page checkout-catalog-page">
        <RequireAuth><CheckoutView /></RequireAuth>
      </main>
      <Footer />
    </>
  );
}
