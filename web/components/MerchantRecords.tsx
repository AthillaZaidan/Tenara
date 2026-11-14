"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronRight, ClipboardList, Package, Scissors, Search, ShoppingBag, X } from "lucide-react";
import { WorkspaceEmpty, WorkspaceError, WorkspaceLoading, WorkspacePage } from "@/components/PartnerWorkspace";
import { useLoad } from "@/components/ui";
import { api, idr, when } from "@/lib/api";
import { REQUEST_STATUS } from "@/lib/design";
import { statusLabel } from "@/lib/orderFlow";
import "@/app/merchant/merchant.css";

type Order = { id: string; kind: string; status: string; total_idr: number; created_at: string; title: string | null };
type Request = { id: string; status: string; submitted_at: string | null; selling_unit?: string | null; requested_quantity?: string | number | null; estimate?: { purchase_quantity?: string | number | null; selling_unit?: string | null } | null };
type RecordItem = { id: string; title: string; subtitle: string; date: string | null; status: string; statusText: string; amount: string | null; href: string };
type Role = "buyer" | "merchant" | "tailor" | "admin";

async function loadAll<T>(path: string): Promise<T[]> {
  let cursor: string | null = null;
  const items: T[] = [];
  do {
    const page: { items: T[]; next_cursor?: string | null } = await api(`${path}&limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`);
    items.push(...page.items);
    cursor = page.next_cursor ?? null;
  } while (cursor);
  return items;
}

export function MerchantRecords({ kind, roles, workspace = "merchant" }: { kind: "orders" | "requests"; roles: Role[]; workspace?: "merchant" | "tailor" }) {
  const isOrders = kind === "orders";
  const tailor = workspace === "tailor";
  const title = isOrders ? tailor ? "Pesanan" : "Pesanan masuk" : "Permintaan baju";
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const records = useLoad(async (): Promise<RecordItem[]> => {
    if (isOrders) {
      const orders = await loadAll<Order>(`/orders?as=${workspace}`);
      return orders.map((order) => ({ id: order.id, title: order.title || (tailor ? "Pesanan baju" : "Pesanan kain"), subtitle: order.kind === "custom" ? "Baju custom" : "Kain", date: order.created_at, status: order.status, statusText: statusLabel(order.status), amount: idr(order.total_idr), href: `/orders/${order.id}?as=${workspace}` }));
    }
    const requests = await loadAll<Request>(`/custom-requests?as=${workspace}`);
    return requests.map((request) => {
      const quantity = tailor ? request.estimate?.purchase_quantity : request.requested_quantity;
      const unit = tailor ? request.estimate?.selling_unit : request.selling_unit;
      return { id: request.id, title: `Permintaan baju ${request.id.slice(0, 8)}`, subtitle: quantity != null ? `${quantity} ${unit === "meter" ? "meter" : unit === "piece" ? "potong" : ""}`.trim() : "—", date: request.submitted_at, status: request.status, statusText: REQUEST_STATUS[request.status] ?? request.status.replaceAll("_", " "), amount: null, href: `/requests/${request.id}?as=${workspace}` };
    });
  }, `${kind}:${workspace}`);
  const items = records.data ?? [];
  const visible = items.filter((item) => (status === "all" || item.status === status) && `${item.title} ${item.id} ${item.statusText}`.toLocaleLowerCase("id").includes(search.trim().toLocaleLowerCase("id")));
  const statuses = Array.from(new Map(items.map((item) => [item.status, item.statusText])).entries());
  const hasFilters = search.trim() !== "" || status !== "all";
  const Icon = isOrders ? ShoppingBag : Scissors;

  return <WorkspacePage role={workspace} active={kind} title={title} description={isOrders ? tailor ? "Pantau setiap jahitan, dari pesanan diterima hingga tiba di tangan pembeli." : "Kelola pesanan kain dan siapkan setiap helai untuk pemilik berikutnya." : tailor ? "Tinjau rancangan pembeli dan siapkan penawaran terbaik Anda." : "Tinjau kebutuhan kain dan konfirmasikan ketersediaan koleksi Anda."}>
      {roles.length > 1 && <nav className="records-roles" aria-label="Lihat sebagai"><span>Lihat sebagai</span>{roles.map((role) => <Link key={role} href={`/${kind}?as=${role}`} aria-current={role === workspace ? "page" : undefined}>{{ buyer: "Pembeli", merchant: "Penjual", tailor: "Penjahit", admin: "Admin" }[role]}</Link>)}</nav>}
      <section className="records-panel" aria-labelledby="records-heading">
        <div className="records-panel-heading"><div><h2 id="records-heading">{isOrders ? "Daftar pesanan" : "Daftar permintaan"}</h2><p>{isOrders ? tailor ? "Semua pesanan jahit yang ditujukan kepada Anda." : "Semua pesanan yang terhubung dengan toko Anda." : tailor ? "Semua permintaan baju yang ditujukan kepada Anda." : "Semua permintaan baju yang menggunakan kain Anda."}</p></div><span className="count">{records.data ? `${items.length} ${isOrders ? "pesanan" : "permintaan"}` : "—"}</span></div>
        <div className="records-toolbar">
          <label className="search"><Search size={17} /><input aria-label={isOrders ? "Cari pesanan" : "Cari permintaan"} placeholder={isOrders ? "Cari nama kain atau ID pesanan…" : "Cari ID atau status permintaan…"} value={search} onChange={(event) => setSearch(event.target.value)} />{search && <button type="button" aria-label="Hapus pencarian" onClick={() => setSearch("")}><X size={15} /></button>}</label>
          <label className="records-status"><span>Status</span><select aria-label="Filter status" value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">Semua status</option>{statuses.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        </div>
        {records.error ? <WorkspaceError message={records.error} retry={records.reload} /> : records.loading ? <WorkspaceLoading>Memuat {isOrders ? "pesanan" : "permintaan"}…</WorkspaceLoading> : visible.length === 0 ? <WorkspaceEmpty icon={Icon} title={hasFilters ? "Tidak ada hasil ditemukan" : isOrders ? "Pesanan berikutnya dimulai di sini" : "Rancangan baru akan hadir di sini"} description={hasFilters ? "Coba kata kunci atau status lain untuk melihat hasil." : tailor ? isOrders ? "Pesanan jahit untuk Anda akan muncul di sini. Lengkapi layanan agar pembeli dapat mengenal karya Anda." : "Saat pembeli mengirim rancangan, Anda dapat meninjau kebutuhan dan menyiapkan penawaran di sini." : isOrders ? "Saat pembeli menemukan kain pilihannya, Anda bisa memantau dan memproses pesanannya di sini." : "Permintaan baju yang menggunakan kain Anda akan muncul di sini untuk dikonfirmasi."} {...(hasFilters ? { onReset: () => { setSearch(""); setStatus("all"); } } : { href: tailor ? "/tailor#pola" : "/merchant#koleksi", action: tailor ? "Lihat layanan jahit" : "Lihat koleksi kain" })} /> : <>
          <div className="records-list-label" aria-hidden="true"><span>{isOrders ? "PESANAN" : "PERMINTAAN"}</span><span>TANGGAL</span><span>STATUS</span><span>{isOrders ? "TOTAL" : "KEBUTUHAN KAIN"}</span><span /></div>
          <ul className="records-list">{visible.map((item) => <li key={item.id}><Link href={item.href}>
            <span className="records-item-main"><span className="records-item-icon">{isOrders ? <Package size={20} strokeWidth={1.4} /> : <ClipboardList size={20} strokeWidth={1.4} />}</span><span><strong>{item.title}</strong><small>{isOrders ? `${item.subtitle} · #${item.id.slice(0, 8)}` : `#${item.id.slice(0, 8)}`}</small><small className="records-mobile-date">{item.date ? when(item.date) : "Belum diajukan"}</small></span></span>
            <span className="records-date">{item.date ? when(item.date) : "Belum diajukan"}</span><span><span className="records-badge" data-status={item.status}>{item.statusText}</span></span><span className="records-amount">{item.amount ?? item.subtitle}</span><ChevronRight size={17} className="records-chevron" />
          </Link></li>)}</ul>
          <div className="records-list-footer">Menampilkan {visible.length} dari {items.length} {isOrders ? "pesanan" : "permintaan"}</div>
        </>}
      </section>
  </WorkspacePage>;
}
