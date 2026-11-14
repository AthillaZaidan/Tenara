"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, idr, newKey } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Field, Notice, useAction, useLoad } from "./ui";
import type { Listing } from "./ListingCard";
import { AddressForm } from "./AddressForm";

type Address = { id: string; label: string; recipient_name: string; line1: string; city: string; province: string };
type Template = { code: string; name: string; compatible: boolean; reasons: string[] };

export function BuyPanel({ listing }: { listing: Listing }) {
  const { me, ready } = useAuth();
  const router = useRouter();
  const { busy, error, run } = useAction();
  const meter = listing.selling_unit === "meter";
  const [qty, setQty] = useState(String(listing.min_quantity));
  const here = `/listings/${listing.id}`;

  const addresses = useLoad(() => (me ? api<Address[]>("/addresses") : Promise.resolve([])), me?.id ?? "anon");
  const templates = useLoad(() => api<Template[]>(`/listings/${listing.id}/templates`), listing.id);
  const [addressId, setAddressId] = useState("");
  const chosen = addressId || addresses.data?.[0]?.id || "";
  const [pick, setPick] = useState("");

  if (!ready) return null;
  if (!me) {
    return (
      <div className="listing-login">
        <Link href={`/login?next=${encodeURIComponent(here)}`} className="btn no-underline">Masuk untuk membeli</Link>
        <p>Masuk untuk membeli kain atau menjadikannya baju.</p>
      </div>
    );
  }
  const inStock = listing.stock.in_stock;
  return (
    <div className="listing-buy">
      <div className="listing-buy-main">
        <h2>Beli kain</h2>
          <Field label={`Jumlah (${meter ? "meter" : "potong"}, kelipatan ${listing.quantity_increment})`}>
            <input className="field" type="number" min={listing.min_quantity} step={listing.quantity_increment} value={qty} onChange={(e) => setQty(e.target.value)} />
          </Field>
        <div className="grid gap-2"><label htmlFor="listing-address">Alamat pengiriman</label>
          {addresses.data && addresses.data.length > 0 ? (
            <select id="listing-address" className="field" value={chosen} onChange={(e) => setAddressId(e.target.value)}>
              {addresses.data.map((a) => <option key={a.id} value={a.id}>{a.label}: {a.recipient_name}, {a.line1}, {a.city}</option>)}
            </select>
          ) : <p>Belum ada alamat tersimpan.</p>}
          <AddressForm onCreated={(id) => { setAddressId(id); addresses.reload(); }} />
        </div>
        <div className="listing-subtotal"><span>Subtotal</span><strong>{idr((Number(qty) || 0) * listing.price_idr)}</strong></div>
        <p className="listing-shipping-note">Ongkir dihitung di langkah berikutnya.</p>
        {error && <Notice tone="error">{error}</Notice>}
        <button
          className="btn"
          disabled={busy || !inStock || !chosen}
          onClick={async () => {
            const co = await run(() =>
              api<{ id: string }>("/fabric-checkouts", { body: { listing_id: listing.id, quantity: qty, delivery_address_id: chosen }, idempotencyKey: newKey() }),
            );
            if (co) router.push(`/checkout/${co.id}`);
          }}
        >
          {inStock ? "Lanjut ke pembayaran" : "Stok habis"}
        </button>
      </div>

      <div className="listing-custom">
        <div><h2>Jadikan baju</h2><p>Rancang pakaian dari kain pilihanmu.</p></div>
        {!listing.custom_order_ready ? (
          <p className="text-base">Kain ini belum dapat dipakai untuk pesanan baju: data yang kurang ({listing.missing_for_custom.join(", ") || "tidak diketahui"}).</p>
        ) : (
          <>
            <Field label="Pola pakaian">
              <select className="field" value={pick} onChange={(e) => setPick(e.target.value)}>
                <option value="">Pilih pola…</option>
                {templates.data?.map((t) => <option key={t.code} value={t.code} disabled={!t.compatible}>{t.name}{t.compatible ? "" : ` (tidak cocok: ${t.reasons[0] ?? "-"})`}</option>)}
              </select>
            </Field>
            <button
              className="btn listing-custom-button"
              disabled={busy || !pick}
              onClick={async () => {
                const c = await run(() => api<{ id: string }>("/customizations", { body: { listing_id: listing.id, template_code: pick } }));
                if (c) router.push(`/customize/${c.id}`);
              }}
            >
              Mulai merancang
            </button>
          </>
        )}
      </div>
    </div>
  );
}
