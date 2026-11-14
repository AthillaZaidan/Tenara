"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { ArrowLeft, ArrowUpRight, Layers, LayoutDashboard, MessageCircle, Scissors, ShoppingBag, Store } from "lucide-react";
import { useAuth } from "@/lib/auth";

export type WorkspaceSection = "overview" | "collection" | "orders" | "requests" | "messages";

export function MerchantSidebar({ active, role = "merchant" }: {
  active: WorkspaceSection;
  role?: "merchant" | "tailor";
}) {
  const { me, has } = useAuth();
  const tailor = role === "tailor";
  const navigation = useRef<HTMLElement>(null);
  useEffect(() => {
    const revealActive = () => {
      const nav = navigation.current;
      const selected = nav?.querySelector<HTMLElement>('[aria-current="page"]');
      if (!nav || !selected || nav.scrollWidth <= nav.clientWidth) return;
      nav.scrollLeft = selected.offsetLeft - nav.offsetLeft - (nav.clientWidth - selected.offsetWidth) / 2;
    };
    revealActive();
    window.addEventListener("resize", revealActive);
    return () => window.removeEventListener("resize", revealActive);
  }, [active, role]);
  return <aside className="sidebar"><div className="sidebar-inner">
    <div className="identity">
      <span className="storeIcon">{tailor ? <Scissors size={23} strokeWidth={1.4} aria-hidden="true" /> : <Store size={23} strokeWidth={1.4} aria-hidden="true" />}</span>
      <div><strong>{me?.display_name}</strong><span>{tailor ? "Penjahit Tenara" : "Penjual kain Tenara"}</span></div>
    </div>
    <p className="navLabel">{tailor ? "RUANG PENJAHIT" : "RUANG PENJUAL"}</p>
    <nav ref={navigation} aria-label={tailor ? "Navigasi penjahit" : "Navigasi penjual"} className="navigation">
      <Link href={tailor ? "/tailor" : "/merchant"} className={active === "overview" ? "navActive" : ""} aria-current={active === "overview" ? "page" : undefined}><LayoutDashboard size={18} />Ringkasan</Link>
      <Link href={tailor ? "/tailor#pola" : "/merchant#koleksi"} className={active === "collection" ? "navActive" : ""} aria-current={active === "collection" ? "page" : undefined}>{tailor ? <Scissors size={18} /> : <Layers size={18} />}{tailor ? "Layanan jahit" : "Koleksi kain"}</Link>
      <Link href={`/orders?as=${role}`} className={active === "orders" ? "navActive" : ""} aria-current={active === "orders" ? "page" : undefined}><ShoppingBag size={18} />{tailor ? "Pesanan" : "Pesanan masuk"}</Link>
      <Link href={`/requests?as=${role}`} className={active === "requests" ? "navActive" : ""} aria-current={active === "requests" ? "page" : undefined}><Scissors size={18} />Permintaan baju</Link>
      <Link href={`/messages?as=${role}`} className={active === "messages" ? "navActive" : ""} aria-current={active === "messages" ? "page" : undefined}><MessageCircle size={18} />Pesan</Link>
    </nav>
    <div className="sidebar-bottom"><p>Dari tangan terampil,<br /><em>untuk cerita berikutnya.</em></p>{has(tailor ? "merchant" : "tailor") && <Link href={tailor ? "/merchant" : "/tailor"}>Buka ruang {tailor ? "penjual" : "penjahit"}<ArrowUpRight size={14} /></Link>}<Link href="/galeri"><ArrowLeft size={14} />Kembali ke galeri</Link></div>
    </div>
  </aside>;
}
