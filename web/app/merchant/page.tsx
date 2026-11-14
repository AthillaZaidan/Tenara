"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ArrowDownUp, ArrowRight, ArrowUpRight, BookOpen, Check, ChevronRight,
  ClipboardList, Layers3, Package, Pencil,
  Plus, Search, ShoppingBag, X,
} from "lucide-react";
import { WorkspaceEmpty, WorkspaceLoading, WorkspacePage } from "@/components/PartnerWorkspace";
import { Notice, RequireAuth, useLoad } from "@/components/ui";
import { api, fileUrl, idr } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { statusLabel } from "@/lib/orderFlow";
import type { Listing } from "@/components/ListingCard";
import "./merchant.css";

type MerchantListing = Listing & { status: string };
type Order = { id: string; kind: string; status: string; total_idr: number; created_at: string; title: string };
type Filter = "all" | "published" | "draft" | "archived";
const filters: { value: Filter; label: string }[] = [
  { value: "all", label: "Semua kain" }, { value: "published", label: "Terbit" },
  { value: "draft", label: "Draf" }, { value: "archived", label: "Diarsipkan" },
];
const listingStatus: Record<string, string> = { published: "Terbit", draft: "Draf", archived: "Diarsipkan" };

function stockLabel(item: MerchantListing) {
  if (!item.stock.in_stock) return "Stok kosong";
  return item.selling_unit === "meter"
    ? `${item.stock.total_length_m ?? 0} m`
    : `${item.stock.available_pieces ?? item.stock.pieces} potong`;
}

// Read every page so the dashboard counts and filters reflect the whole collection.
async function loadAll<T>(path: string): Promise<T[]> {
  const items: T[] = [];
  let cursor: string | null = null;
  do {
    const page: { items: T[]; next_cursor?: string | null } = await api(
      `${path}${path.includes("?") ? "&" : "?"}limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`,
    );
    items.push(...page.items);
    cursor = page.next_cursor ?? null;
  } while (cursor);
  return items;
}

function Weave() {
  return <svg className="weave" viewBox="0 0 240 240" fill="none" aria-hidden="true">
    {[0, 1, 2, 3].map((row) => [0, 1, 2, 3].map((col) => (
      <g key={`${row}-${col}`} transform={`translate(${col * 64 - 8} ${row * 64 - 8})`}>
        <path d="M32 0 64 32 32 64 0 32Z M32 12 52 32 32 52 12 32Z M32 24 40 32 32 40 24 32Z" stroke="currentColor" />
        <path d="M0 0 12 12M52 52 64 64M64 0 52 12M12 52 0 64" stroke="currentColor" />
      </g>
    ))) }
  </svg>;
}

function Dashboard() {
  const { me } = useAuth();
  const listings = useLoad(() => loadAll<MerchantListing>("/merchant/listings"));
  const orders = useLoad(() => loadAll<Order>("/orders?as=merchant"));
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("newest");
  const items = listings.data ?? [];
  const published = items.filter((item) => item.status === "published").length;
  const drafts = items.filter((item) => item.status === "draft").length;
  const actionableOrders = (orders.data ?? []).filter((order) => ["confirmed", "preparing", "fabric_preparing"].includes(order.status));
  const visible = items.filter((item) =>
    (filter === "all" || item.status === filter) && item.title.toLocaleLowerCase("id").includes(search.trim().toLocaleLowerCase("id")),
  ).sort((a, b) => sort === "name" ? a.title.localeCompare(b.title, "id") : sort === "price" ? a.price_idr - b.price_idr : 0);
  const recentOrders = [...(orders.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 3);
  const resetFilters = () => { setFilter("all"); setSearch(""); };
  const stats = [
    { label: "Kain terbit", value: published, note: "Tampil di etalase Tenara", icon: Layers3, href: "#koleksi", onClick: () => { setFilter("published"); setSearch(""); } },
    { label: "Pesanan perlu diproses", value: actionableOrders.length, note: "Siapkan dan kirim kain Anda", icon: ShoppingBag, href: "/orders?as=merchant" },
    { label: "Draf kain", value: drafts, note: "Lanjutkan sebelum diterbitkan", icon: Pencil, href: "#koleksi", onClick: () => { setFilter("draft"); setSearch(""); } },
  ];

  return (
    <WorkspacePage role="merchant" title="Ringkasan toko" description="Rawat koleksi, sambut pesanan, dan kembangkan usaha Anda." action={<Link href="/merchant/listings/new" className="btn addButton"><Plus size={17} />Tambah kain</Link>}>

        <section className="welcome" aria-label="Selamat datang">
          <div><span className="welcomeLabel"><span />SETIAP HELAI, SEBUAH PELUANG</span><h2>Selamat berkarya, {me?.display_name}.</h2><p>Dari koleksi Anda, lahir cerita baru untuk pemilik berikutnya.</p><a href="#koleksi">Lihat koleksi Anda<ArrowRight size={17} /></a></div>
          <div className="welcomeArt"><Weave /><span>Terhubung oleh benang.<br /><em>Bertumbuh lewat cerita.</em></span></div>
        </section>

        <section className="stats" aria-label="Ringkasan toko">
          {stats.map(({ label, value, note, icon: Icon, href, onClick }, index) => {
            const source = index === 1 ? orders : listings;
            return <a key={label} href={href} onClick={onClick} className="stat">
              <div><span>{label}</span><Icon size={19} strokeWidth={1.5} /></div>
              <strong>{source.loading || source.error ? "—" : value.toLocaleString("id-ID")}</strong>
              <p>{source.error ? "Data belum tersedia" : note}<ArrowUpRight size={14} /></p>
            </a>;
          })}
        </section>

        <div className="workspace">
          <section id="koleksi" className="collection" aria-labelledby="collection-heading">
            <div className="sectionHeading"><div><h2 id="collection-heading">Koleksi kain</h2><p>Setiap helai, siap menemukan pemiliknya.</p></div><span className="count">{listings.data ? `${items.length} kain` : "—"}</span></div>
            <div className="filters" aria-label="Filter status kain">
              {filters.map(({ value, label }) => <button key={value} type="button" aria-pressed={filter === value} onClick={() => setFilter(value)} className={filter === value ? "filterActive" : ""}>{label}<span>{listings.data ? value === "all" ? items.length : items.filter((item) => item.status === value).length : "—"}</span></button>)}
            </div>
            <div className="toolbar">
              <label className="search"><Search size={17} /><input aria-label="Cari nama kain" placeholder="Cari nama kain…" value={search} onChange={(event) => setSearch(event.target.value)} />{search && <button type="button" aria-label="Hapus pencarian" onClick={() => setSearch("")}><X size={15} /></button>}</label>
              <label className="sort"><ArrowDownUp size={15} /><select aria-label="Urutkan kain" value={sort} onChange={(event) => setSort(event.target.value)}><option value="newest">Terbaru</option><option value="name">Nama A–Z</option><option value="price">Harga terendah</option></select></label>
            </div>
            {listings.error ? <div className="loadState"><Notice tone="error">{listings.error}</Notice><button type="button" className="btn btn-quiet" onClick={listings.reload}>Coba lagi</button></div> : listings.loading ? <WorkspaceLoading>Menyiapkan koleksi Anda…</WorkspaceLoading> : visible.length === 0 ? <WorkspaceEmpty icon={Layers3} title={items.length ? "Kain belum ditemukan" : "Cerita pertama dimulai di sini"} description={items.length ? "Coba kata kunci lain atau tampilkan semua kain Anda." : "Tambahkan kain pertama dan perkenalkan karya Anda kepada lebih banyak orang."} {...(items.length ? { onReset: resetFilters } : { href: "/merchant/listings/new", action: "Tambah kain pertama" })} /> : <>
              <div className="tableWrap"><table className="table"><thead><tr><th scope="col">Kain</th><th scope="col">Harga</th><th scope="col">Stok tersedia</th><th scope="col">Status</th><th scope="col"><span className="srOnly">Kelola</span></th></tr></thead><tbody>
                {visible.map((item) => <tr key={item.id}>
                  <td><Link href={`/merchant/listings/${item.id}`} className="product">{item.images[0] ? <img src={fileUrl(item.images[0].url)} alt={item.images[0].caption ?? item.title} width={56} height={64} /> : <span className="noPhoto"><Layers3 size={21} strokeWidth={1.3} /></span>}<span><strong>{item.title}</strong><small>{item.material ?? "Kain tenun"} · {item.selling_unit === "meter" ? "Per meter" : "Per potong"}</small><small className="mobileProductMeta">{idr(item.price_idr)} · {stockLabel(item)}</small></span></Link></td>
                  <td className="price">{idr(item.price_idr)}<small>/ {item.selling_unit === "meter" ? "meter" : "potong"}</small></td>
                  <td><span className={!item.stock.in_stock ? "outOfStock" : ""}>{stockLabel(item)}</span></td>
                  <td><span className={`badge ${item.status === "published" ? "published" : item.status === "draft" ? "draft" : "archived"}`}>{item.status === "published" && <span />}{listingStatus[item.status] ?? item.status}</span></td>
                  <td><Link href={`/merchant/listings/${item.id}`} className="editButton" aria-label={`Kelola ${item.title}`}><Pencil size={16} /></Link></td>
                </tr>)}
              </tbody></table></div><div className="tableFooter"><span>Menampilkan {visible.length} dari {items.length} kain</span><span><Check size={13} />Terhubung dengan etalase Anda</span></div>
            </>}
            <Link href="/merchant/listings/new" className="addCollection"><Plus size={17} />Tambahkan karya berikutnya</Link>
          </section>

          <aside className="rightColumn">
            <section className="orders" aria-labelledby="orders-heading">
              <div className="panelHeading"><h2 id="orders-heading">Pesanan terbaru</h2><ShoppingBag size={19} strokeWidth={1.4} /></div>
              {orders.error ? <div className="orderEmpty orderError"><div><p role="alert">{orders.error}</p><button type="button" onClick={orders.reload}>Coba lagi<ArrowRight size={14} /></button></div></div> : orders.loading ? <p className="orderLoading" role="status">Memuat pesanan…</p> : recentOrders.length ? <ul className="orderList">{recentOrders.map((order) => <li key={order.id}><Link href={`/orders/${order.id}?as=merchant`}><span className="orderIcon"><Package size={18} /></span><span><strong>{order.title || "Pesanan kain"}</strong><small>{statusLabel(order.status)}</small><b>{idr(order.total_idr)}</b></span><ChevronRight size={15} /></Link></li>)}</ul> : <div className="orderEmpty"><span className="emptyBag"><ShoppingBag size={22} strokeWidth={1.3} /></span><div><h3>Belum ada pesanan</h3><p>Pesanan yang masuk akan tampil di sini.</p></div></div>}
              <Link href="/orders?as=merchant" className="panelLink">Lihat semua pesanan<ArrowRight size={16} /></Link>
            </section>
            <section className="tip">
              <span className="tipLabel"><BookOpen size={16} />CATATAN UNTUK MITRA</span><h2>Kain yang bercerita, lebih dekat di hati.</h2><p>Foto yang jelas, ukuran yang lengkap, dan kisah di balik motif membantu pembeli mengenal karya Anda.</p><Link href="/merchant/listings/new">Mulai dari sehelai kain<ArrowUpRight size={16} /></Link>
            </section>
            <Link href="/requests?as=merchant" className="requestLink"><span><ClipboardList size={19} /><span>Permintaan baju<small>Tindak lanjuti kebutuhan kain pembeli</small></span></span><ArrowUpRight size={17} /></Link>
          </aside>
        </div>
    </WorkspacePage>
  );
}

export default function MerchantPage() {
  return <RequireAuth role="merchant" loadingFallback={<WorkspaceLoading />}><Dashboard /></RequireAuth>;
}
