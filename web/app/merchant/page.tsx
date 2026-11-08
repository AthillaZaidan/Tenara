"use client";

import Link from "next/link";
import { Notice, Page, RequireAuth, useLoad } from "@/components/ui";
import { api, idr } from "@/lib/api";
import type { Listing } from "@/components/ListingCard";

function Dashboard() {
  const { data, error, loading } = useLoad(() => api<{ items: (Listing & { status: string })[] }>("/merchant/listings"));
  return (
    <div className="grid gap-10">
      <div className="flex flex-wrap gap-3">
        <Link href="/merchant/listings/new" className="btn no-underline">Tambah kain</Link>
        <Link href="/orders?as=merchant" className="btn btn-quiet no-underline">Pesanan masuk</Link>
        <Link href="/requests?as=merchant" className="btn btn-quiet no-underline">Permintaan baju</Link>
      </div>
      {error && <Notice tone="error">{error}</Notice>}
      {loading ? <p>Memuat…</p> : data?.items.length === 0 ? <p>Belum ada kain. Tambahkan yang pertama.</p> : (
        <ul className="grid max-w-3xl list-none gap-0 p-0">
          {data?.items.map((l) => (
            <li key={l.id}>
              <Link href={`/merchant/listings/${l.id}`} className="group grid grid-cols-[1fr_auto] gap-x-6 py-4 no-underline">
                <span className="text-lg group-hover:underline underline-offset-4">{l.title}</span>
                <span className="text-lg">{idr(l.price_idr)}</span>
                <span className="text-base text-muted">{l.stock.in_stock ? (l.selling_unit === "meter" ? `${l.stock.total_length_m} m` : `${l.stock.pieces} potong`) : "Stok kosong"}</span>
                <span className="text-base text-right">{{ draft: "Draf", published: "Terbit", archived: "Diarsipkan" }[l.status] ?? l.status}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function MerchantPage() {
  return (
    <Page>
      <h1 className="t-head mb-10 mt-8">Dasbor penjual</h1>
      <RequireAuth role="merchant"><Dashboard /></RequireAuth>
    </Page>
  );
}
