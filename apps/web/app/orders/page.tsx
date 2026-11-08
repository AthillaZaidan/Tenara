"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Notice, Page, RequireAuth, useLoad } from "@/components/ui";
import { api, idr, when } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { statusLabel } from "@/lib/orderFlow";

type Row = { id: string; kind: string; status: string; total_idr: number; created_at: string; title: string };

function List() {
  const { has } = useAuth();
  const roles = (["buyer", "merchant", "tailor", "admin"] as const).filter((r) => has(r));
  const asParam = useSearchParams().get("as");
  const as = roles.find((r) => r === asParam) ?? roles[0] ?? "buyer";
  const { data, error, loading } = useLoad(() => api<{ items: Row[] }>(`/orders?as=${as}`), as);
  return (
    <>
      {roles.length > 1 && (
        <p className="mb-8 flex flex-wrap gap-4 text-base">
          {roles.map((r) => (
            <Link key={r} href={`/orders?as=${r}`} className={r === as ? "link font-medium" : "no-underline hover:underline underline-offset-4"}>
              {{ buyer: "Sebagai pembeli", merchant: "Sebagai penjual", tailor: "Sebagai penjahit", admin: "Semua (admin)" }[r]}
            </Link>
          ))}
        </p>
      )}
      {error && <Notice tone="error">{error}</Notice>}
      {loading ? <p>Memuat…</p> : data && data.items.length === 0 ? (
        <div className="grid gap-4"><p>Belum ada pesanan.</p><Link href="/gallery" className="btn w-fit no-underline">Jelajahi Gallery</Link></div>
      ) : (
        <ul className="grid max-w-3xl list-none gap-0 p-0">
          {data?.items.map((o) => (
            <li key={o.id}>
              <Link href={`/orders/${o.id}?as=${as}`} className="group grid grid-cols-[1fr_auto] gap-x-6 gap-y-1 py-4 no-underline">
                <span className="text-lg group-hover:underline underline-offset-4">{o.title}</span>
                <span className="text-lg">{idr(o.total_idr)}</span>
                <span className="text-base text-muted">{o.kind === "custom" ? "Baju custom" : "Kain"} · {when(o.created_at)}</span>
                <span className="text-base text-right">{statusLabel(o.status)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

export default function OrdersPage() {
  return (
    <Page>
      <h1 className="t-head mb-10 mt-8">Pesanan</h1>
      <RequireAuth><Suspense fallback={null}><List /></Suspense></RequireAuth>
    </Page>
  );
}
