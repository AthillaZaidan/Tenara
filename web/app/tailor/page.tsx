"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, ArrowUpRight, BookOpen, ChevronDown, ChevronRight, ClipboardList, Package, Scissors, Search, Shirt, ShoppingBag, X } from "lucide-react";
import { WorkspaceEmpty, WorkspaceLoading, WorkspacePage } from "@/components/PartnerWorkspace";
import { Notice, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api, idr } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { actionsFor, statusLabel } from "@/lib/orderFlow";
import "@/app/merchant/merchant.css";
import "./tailor.css";

type Cap = { template_code: string; base_rate_idr: number; lead_time_days: number; weekly_capacity: number; materials: string[]; supported_options?: Record<string, unknown> };
type Tpl = { code: string; name: string };
type Order = { id: string; kind: string; status: string; total_idr: number; created_at: string; title: string | null };
type Request = { id: string };

async function loadAll<T>(path: string): Promise<T[]> {
  const items: T[] = [];
  let cursor: string | null = null;
  do {
    const page: { items: T[]; next_cursor?: string | null } = await api(`${path}&limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`);
    items.push(...page.items);
    cursor = page.next_cursor ?? null;
  } while (cursor);
  return items;
}

function CapabilityRow({ tpl, cap, reload }: { tpl: Tpl; cap?: Cap; reload: () => void }) {
  const act = useAction();
  const [open, setOpen] = useState(false);
  const [rate, setRate] = useState(String(cap?.base_rate_idr ?? ""));
  const [lead, setLead] = useState(String(cap?.lead_time_days ?? 14));
  const [week, setWeek] = useState(String(cap?.weekly_capacity ?? 3));
  const [mats, setMats] = useState((cap?.materials ?? ["katun", "tenun"]).join(", "));
  return <li className="tailor-pattern">
    <button className="tailor-pattern-toggle" type="button" aria-expanded={open} aria-controls={`service-${tpl.code}`} onClick={() => setOpen(!open)}>
      <span className="tailor-pattern-icon"><Shirt size={20} strokeWidth={1.4} /></span>
      <span className="tailor-pattern-name"><strong>{tpl.name}</strong><small>{tpl.code}{cap ? ` · ${idr(cap.base_rate_idr)} / baju` : " · Atur layanan untuk mulai menawarkan"}</small></span>
      <span className={`badge ${cap ? "published" : "archived"}`}>{cap ? "Ditawarkan" : "Belum ditawarkan"}</span><ChevronDown className={open ? "tailor-chevron-open" : ""} size={17} />
    </button>
    {open && <form id={`service-${tpl.code}`} className="tailor-form" onSubmit={async (e) => { e.preventDefault(); const result = await act.run(() => api(`/tailor/capabilities/${tpl.code}`, { method: "PUT", body: { base_rate_idr: Number(rate), lead_time_days: Number(lead), weekly_capacity: Number(week), materials: mats.split(",").map((m) => m.trim()).filter(Boolean), supported_options: cap?.supported_options ?? {} } })); if (result !== undefined) { setOpen(false); reload(); } }}>
      <div className="tailor-service-intro"><h3>Detail layanan</h3><p>Tarif dan waktu pengerjaan ini membantu pembeli memilih layanan Anda.</p></div>
      <div className="tailor-fields">
        <label>Tarif dasar (Rp)<input className="field" type="number" min="1" required value={rate} onChange={(e) => setRate(e.target.value)} placeholder="Contoh: 300000" /></label>
        <label>Lama pengerjaan (hari)<input className="field" type="number" min="1" max="365" required value={lead} onChange={(e) => setLead(e.target.value)} /></label>
        <label>Kapasitas per minggu<input className="field" type="number" min="1" max="1000" required value={week} onChange={(e) => setWeek(e.target.value)} /></label>
        <label>Bahan yang diterima<input className="field" value={mats} onChange={(e) => setMats(e.target.value)} placeholder="Contoh: katun, tenun" /><small>Pisahkan setiap bahan dengan koma.</small></label>
      </div>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <div className="tailor-form-actions"><button className="btn" disabled={act.busy}>{act.busy ? "Menyimpan…" : cap ? "Simpan perubahan" : "Tawarkan layanan"}</button><button type="button" className="tailor-cancel" disabled={act.busy} onClick={() => setOpen(false)}>Tutup</button>{cap && <button type="button" className="tailor-stop" disabled={act.busy} onClick={async () => { const result = await act.run(() => api(`/tailor/capabilities/${tpl.code}`, { method: "DELETE" })); if (result !== undefined) { setOpen(false); reload(); } }}>Hentikan penawaran</button>}</div>
    </form>}
  </li>;
}

function Dashboard() {
  const { me } = useAuth();
  const caps = useLoad(() => api<Cap[]>("/tailor/capabilities"));
  const tpls = useLoad(() => api<Tpl[]>("/garment-templates"));
  const orders = useLoad(() => loadAll<Order>("/orders?as=tailor"));
  const requests = useLoad(() => loadAll<Request>("/custom-requests?as=tailor"));
  const [filter, setFilter] = useState<"all" | "offered" | "available">("all");
  const [search, setSearch] = useState("");
  const patterns = tpls.data ?? [];
  const offered = caps.data ?? [];
  const visible = patterns.filter((tpl) => (filter === "all" || (filter === "offered") === offered.some((cap) => cap.template_code === tpl.code)) && `${tpl.name} ${tpl.code}`.toLocaleLowerCase("id").includes(search.trim().toLocaleLowerCase("id")));
  const recent = [...(orders.data ?? [])].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 3);
  const actionable = (orders.data ?? []).filter((order) => actionsFor(order.kind, order.status, "tailor").length > 0).length;
  const filterOptions = [{ value: "all" as const, label: "Semua pola", count: patterns.length }, { value: "offered" as const, label: "Ditawarkan", count: offered.length }, { value: "available" as const, label: "Belum ditawarkan", count: patterns.filter((tpl) => !offered.some((cap) => cap.template_code === tpl.code)).length }];
  return <WorkspacePage role="tailor" title="Ringkasan studio" description="Kelola layanan jahit dan temukan peluang dari setiap rancangan." action={<a href="#pola" className="btn addButton"><Scissors size={17} />Kelola layanan</a>}>
      <section className="welcome" aria-label="Selamat datang"><div><span className="welcomeLabel"><span />SETIAP JAHITAN, SEBUAH CERITA</span><h2>Selamat berkarya, {me?.display_name}.</h2><p>Wujudkan ide pembeli dengan keterampilan dan sentuhan khas Anda.</p><a href="#pola">Lihat layanan Anda<ArrowRight size={17} /></a></div><div className="welcomeArt tailor-welcome-art" aria-hidden="true"><Scissors size={120} strokeWidth={0.7} /><span>Terhubung oleh benang.<br /><em>Bertumbuh lewat cerita.</em></span></div></section>
      <section className="stats" aria-label="Ringkasan usaha">
        {[{ label: "Pola ditawarkan", value: offered.length, note: "Layanan yang tersedia untuk pembeli", icon: Shirt, href: "#pola", source: caps }, { label: "Pesanan perlu diproses", value: actionable, note: "Lihat pekerjaan yang menunggu", icon: ShoppingBag, href: "/orders?as=tailor", source: orders }, { label: "Permintaan baju", value: requests.data?.length ?? 0, note: "Lihat seluruh permintaan", icon: ClipboardList, href: "/requests?as=tailor", source: requests }].map(({ label, value, note, icon: Icon, href, source }) => <a key={label} href={href} className="stat"><div><span>{label}</span><Icon size={19} strokeWidth={1.5} /></div><strong>{source.loading || source.error ? "—" : value.toLocaleString("id-ID")}</strong><p>{source.error ? "Data belum tersedia" : note}<ArrowUpRight size={14} /></p></a>)}
      </section>
      <div className="workspace">
        <section id="pola" className="collection" aria-labelledby="patterns-heading"><div className="sectionHeading"><div><h2 id="patterns-heading">Layanan jahit</h2><p>Pilih pola pakaian dan atur detail layanan Anda.</p></div><span className="count">{tpls.data ? `${patterns.length} pola` : "—"}</span></div>
          <div className="filters" aria-label="Filter pola">{filterOptions.map((option) => <button key={option.value} type="button" className={filter === option.value ? "filterActive" : ""} aria-pressed={filter === option.value} onClick={() => setFilter(option.value)}>{option.label}<span>{caps.data && tpls.data ? option.count : "—"}</span></button>)}</div>
          <div className="toolbar"><label className="search"><Search size={17} /><input aria-label="Cari pola pakaian" placeholder="Cari nama atau kode pola…" value={search} onChange={(e) => setSearch(e.target.value)} />{search && <button type="button" aria-label="Hapus pencarian" onClick={() => setSearch("")}><X size={15} /></button>}</label></div>
          {caps.error || tpls.error ? <div className="loadState"><Notice tone="error">{caps.error ?? tpls.error}</Notice><button type="button" className="btn btn-quiet" onClick={() => { caps.reload(); tpls.reload(); }}>Coba lagi</button></div> : caps.loading || tpls.loading ? <WorkspaceLoading>Memuat pola pakaian…</WorkspaceLoading> : visible.length ? <><ul className="tailor-patterns">{visible.map((tpl) => { const cap = offered.find((item) => item.template_code === tpl.code); return <CapabilityRow key={`${tpl.code}:${JSON.stringify(cap ?? null)}`} tpl={tpl} cap={cap} reload={caps.reload} />; })}</ul><div className="tableFooter"><span>Menampilkan {visible.length} dari {patterns.length} pola</span></div></> : <WorkspaceEmpty icon={Shirt} title={patterns.length ? "Pola belum ditemukan" : "Belum ada pola tersedia"} description={patterns.length ? "Coba kata kunci atau filter lain." : "Pola pakaian akan muncul di sini saat tersedia."} onReset={patterns.length ? () => { setSearch(""); setFilter("all"); } : undefined} />}
        </section>
        <aside className="rightColumn"><section className="orders"><div className="panelHeading"><h2>Pesanan terbaru</h2><ShoppingBag size={19} strokeWidth={1.4} /></div>{orders.error ? <div className="orderEmpty orderError"><div><p role="alert">{orders.error}</p><button type="button" onClick={orders.reload}>Coba lagi<ArrowRight size={14} /></button></div></div> : orders.loading ? <p className="orderLoading" role="status">Memuat pesanan…</p> : recent.length ? <ul className="orderList">{recent.map((order) => <li key={order.id}><Link href={`/orders/${order.id}?as=tailor`}><span className="orderIcon"><Package size={18} /></span><span><strong>{order.title || "Pesanan baju"}</strong><small>{statusLabel(order.status)}</small><b>{idr(order.total_idr)}</b></span><ChevronRight size={15} /></Link></li>)}</ul> : <div className="orderEmpty"><span className="emptyBag"><ShoppingBag size={22} strokeWidth={1.3} /></span><div><h3>Belum ada pesanan</h3><p>Pesanan yang masuk akan tampil di sini.</p></div></div>}<Link href="/orders?as=tailor" className="panelLink">Lihat semua pesanan<ArrowRight size={16} /></Link></section>
          <section className="tip"><span className="tipLabel"><BookOpen size={16} />CATATAN UNTUK MITRA</span><h2>Setiap jahitan membawa cerita.</h2><p>Lengkapi tarif, waktu pengerjaan, dan bahan yang Anda terima agar pembeli lebih mudah mengenal layanan Anda.</p><a href="#pola">Atur pola pakaian<ArrowUpRight size={16} /></a></section>
          <Link href="/requests?as=tailor" className="requestLink"><span><ClipboardList size={19} /><span>Permintaan baju<small>Tinjau kebutuhan baju dari pembeli</small></span></span><ArrowUpRight size={17} /></Link>
        </aside>
      </div>
  </WorkspacePage>;
}

export default function TailorPage() {
  return <RequireAuth role="tailor" loadingFallback={<WorkspaceLoading />}><Dashboard /></RequireAuth>;
}
