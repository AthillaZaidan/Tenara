"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ChevronRight, Package, ShoppingBag } from "lucide-react";
import { Notice, RequireAuth, useLoad } from "@/components/ui";
import { CollectionEmptyState, CollectionLoading, PersonalCollection } from "@/components/PersonalCollection";
import { api, idr, when } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { statusLabel } from "@/lib/orderFlow";
import { MerchantRecords } from "@/components/MerchantRecords";

type Row = { id: string; kind: string; status: string; total_idr: number; created_at: string; title: string };

function List() {
  const { has } = useAuth();
  const roles = (["buyer", "merchant", "tailor", "admin"] as const).filter((r) => has(r));
  const asParam = useSearchParams().get("as");
  const as = roles.find((r) => r === asParam) ?? roles[0] ?? "buyer";
  const { data, error, loading, reload } = useLoad(() => api<{ items: Row[] }>(`/orders?as=${as}`), as);
  return (
    <section className="personal-panel" aria-label="Daftar pesanan">
      <div className="personal-panel-heading personal-panel-heading--tabs">
      {roles.length > 1 ? (
        <nav className="personal-role-tabs" aria-label="Lihat pesanan sebagai">
          {roles.map((r) => (
            <Link key={r} href={`/orders?as=${r}`} aria-current={r === as ? "page" : undefined} aria-label={{ buyer: "Sebagai pembeli", merchant: "Sebagai penjual", tailor: "Sebagai penjahit", admin: "Semua (admin)" }[r]}>
              {{ buyer: "Pembeli", merchant: "Penjual", tailor: "Penjahit", admin: "Semua (admin)" }[r]}
            </Link>
          ))}
        </nav>
      ) : <div className="personal-panel-title"><ShoppingBag size={17} strokeWidth={1.5} aria-hidden="true" /><h2>{as === "admin" ? "Semua pesanan" : "Pesanan Anda"}</h2></div>}
      <span className="personal-count">{data ? `${data.items.length} pesanan` : "—"}</span>
      </div>
      {error ? <div className="personal-feedback"><Notice tone="error">{error}</Notice><button className="btn btn-quiet" onClick={reload}>Coba lagi</button></div> : loading ? <CollectionLoading>Memuat pesanan…</CollectionLoading> : data && data.items.length === 0 ? (
        <CollectionEmptyState kind="orders" title={as === "admin" ? "Belum ada pesanan" : "Cerita pesanan Anda dimulai di sini"} description={as === "admin" ? "Pesanan akan muncul di sini setelah pembeli melakukan pemesanan." : "Belum ada pesanan. Jelajahi kain Nusantara dan temukan karya yang ingin Anda bawa pulang."} href="/galeri" action="Jelajahi Nusantara" />
      ) : (
        <ul className="personal-orders">
          {data?.items.map((o) => (
            <li key={o.id}>
              <Link href={`/orders/${o.id}?as=${as}`} className="personal-order">
                <span className="personal-order-icon"><Package size={20} strokeWidth={1.4} aria-hidden="true" /></span>
                <span className="personal-order-details"><span className="personal-order-title">{o.title || (o.kind === "custom" ? "Baju custom" : "Pesanan kain")}</span><span className="personal-order-meta">{o.kind === "custom" ? "Baju custom" : "Kain"} · {when(o.created_at)}</span></span>
                <span className="personal-order-summary"><span>{idr(o.total_idr)}</span><span className="personal-order-status">{statusLabel(o.status)}</span></span>
                <ChevronRight className="personal-order-chevron" size={16} aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function OrdersPage() {
  return <Suspense fallback={null}><RequireAuth><OrdersView /></RequireAuth></Suspense>;
}

function OrdersView() {
  const { has } = useAuth();
  const roles = (["buyer", "merchant", "tailor", "admin"] as const).filter((role) => has(role));
  const asParam = useSearchParams().get("as");
  const as = roles.find((role) => role === asParam) ?? roles[0] ?? "buyer";
  if (as === "merchant" || as === "tailor") return <MerchantRecords key={as} kind="orders" roles={roles} workspace={as} />;
  return <PersonalCollection title="Pesanan" description="Ikuti perjalanan kain dan busana pilihan Anda, dari pengrajin hingga tiba di rumah."><List key={as} /></PersonalCollection>;
}
