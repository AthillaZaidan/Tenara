"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, idr, newKey } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Field, Notice, useAction, useLoad } from "./ui";
import type { Listing } from "./ListingCard";

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
      <div className="grid gap-4 bg-surface p-6">
        <p>Masuk untuk membeli kain ini atau menjadikannya baju.</p>
        <Link href={`/login?next=${encodeURIComponent(here)}`} className="btn w-fit no-underline">Masuk</Link>
      </div>
    );
  }
  const inStock = listing.stock.in_stock;
  const addAddress = async () => {
    const created = await run(() =>
      api<Address>("/addresses", { body: { label: "Rumah", recipient_name: me.display_name, phone: "081200000000", line1: "Jl. Contoh No. 1", city: "Jakarta", province: "DKI Jakarta", postal_code: "10110" } }),
    );
    if (created) {
      setAddressId(created.id);
      addresses.reload();
    }
  };

  return (
    <div className="grid gap-8">
      <div className="grid gap-5 bg-surface p-6">
        <h2 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Beli kainnya saja</h2>
        {meter && (
          <Field label={`Jumlah (meter, kelipatan ${listing.quantity_increment})`}>
            <input className="field" type="number" min={listing.min_quantity} step={listing.quantity_increment} value={qty} onChange={(e) => setQty(e.target.value)} />
          </Field>
        )}
        <Field label="Alamat pengiriman">
          {addresses.data && addresses.data.length > 0 ? (
            <select className="field" value={chosen} onChange={(e) => setAddressId(e.target.value)}>
              {addresses.data.map((a) => <option key={a.id} value={a.id}>{a.label}: {a.recipient_name}, {a.line1}, {a.city}</option>)}
            </select>
          ) : (
            <button type="button" className="btn btn-quiet w-fit" onClick={addAddress} disabled={busy}>Tambah alamat contoh</button>
          )}
        </Field>
        <p className="text-base">
          Harga {idr(listing.price_idr)} per {meter ? "meter" : "potong"}
          {meter && !Number.isNaN(Number(qty)) && <> · subtotal {idr(Number(qty) * listing.price_idr)}</>}. Ongkir dihitung di langkah berikutnya.
        </p>
        {error && <Notice tone="error">{error}</Notice>}
        <button
          className="btn"
          disabled={busy || !inStock || !chosen}
          onClick={async () => {
            const co = await run(() =>
              api<{ id: string }>("/fabric-checkouts", { body: { listing_id: listing.id, quantity: meter ? qty : "1", delivery_address_id: chosen }, idempotencyKey: newKey() }),
            );
            if (co) router.push(`/checkout/${co.id}`);
          }}
        >
          {inStock ? "Lanjut ke pembayaran" : "Stok habis"}
        </button>
      </div>

      <div className="grid gap-5 bg-surface p-6">
        <h2 className="text-xl font-medium" style={{ fontFamily: "var(--font-hanken)" }}>Jadikan baju</h2>
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
              className="btn"
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
