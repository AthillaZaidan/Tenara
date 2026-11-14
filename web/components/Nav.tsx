"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { ArrowUpRight, Heart, Menu, ShoppingBag, UserRound, X } from "lucide-react";
import { useAuth } from "@/lib/auth";

export function Nav({ onField = false }: { onField?: boolean }) {
  const { me, logout, has } = useAuth();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const links = [
    { label: "Galeri", href: "/galeri" },
    { label: "Katalog Kain", href: "/katalog" },
  ];
  const active = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <header className={`site-header ${onField ? "on-field" : ""}`}>
      <div className="site-header-inner">
        <Link href="/galeri" className="site-brand" aria-label="Tenara — jelajahi Nusantara">
          <svg viewBox="0 0 36 36" fill="none" aria-hidden="true">
            <path d="M18 2 34 18 18 34 2 18Z" stroke="currentColor" strokeWidth="1.4" />
            <path d="m18 8 10 10-10 10L8 18Zm0 6 4 4-4 4-4-4ZM7 7l22 22M29 7 7 29" stroke="currentColor" strokeWidth="1.2" />
          </svg>
          <span>Tenara</span>
        </Link>

        <nav className="site-nav" aria-label="Navigasi utama">
          {links.map((link) => (
            <Link key={link.href} href={link.href} className={active(link.href) ? "active" : ""}>
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="site-actions">
          <Link href={me ? "/designs" : "/login"} className="site-icon-button" aria-label="Desain tersimpan" title="Desain tersimpan">
            <Heart size={20} strokeWidth={1.7} />
          </Link>
          <Link href={me ? "/orders" : "/login"} className="site-icon-button" aria-label="Pesanan saya" title="Pesanan saya">
            <ShoppingBag size={20} strokeWidth={1.7} />
          </Link>
          {me ? (
            <details className="site-account-menu">
              <summary className="site-icon-button" aria-label="Menu akun" title="Menu akun">
                <UserRound size={20} strokeWidth={1.7} />
              </summary>
              <div className="site-account-popover">
                <span>{me.display_name}</span>
                <Link href="/account">Akun saya</Link>
                <Link href="/requests">Baju custom</Link>
                <Link href="/messages">Pesan</Link>
                {has("merchant") && <Link href="/merchant">Ruang penjual</Link>}
                {has("tailor") && <Link href="/tailor">Ruang penjahit</Link>}
                {has("admin") && <Link href="/admin">Ruang admin</Link>}
                <button type="button" onClick={logout}>Keluar</button>
              </div>
            </details>
          ) : (
            <Link href="/login" className="site-icon-button" aria-label="Masuk ke akun" title="Masuk ke akun">
              <UserRound size={20} strokeWidth={1.7} />
            </Link>
          )}
          <button
            type="button"
            className="site-icon-button site-menu-button"
            aria-label={mobileOpen ? "Tutup menu" : "Buka menu"}
            aria-expanded={mobileOpen}
            aria-controls="site-mobile-navigation"
            onClick={() => setMobileOpen((open) => !open)}
          >
            {mobileOpen ? <X size={21} /> : <Menu size={21} />}
          </button>
        </div>
      </div>
      {mobileOpen && (
        <nav className="site-mobile-nav" id="site-mobile-navigation" aria-label="Navigasi mobile">
          {links.map((link) => (
            <Link key={link.href} href={link.href} onClick={() => setMobileOpen(false)}>
              {link.label}<ArrowUpRight size={16} aria-hidden="true" />
            </Link>
          ))}
          {me ? (
            <>
              <Link href="/orders" onClick={() => setMobileOpen(false)}>Pesanan <ArrowUpRight size={16} aria-hidden="true" /></Link>
              <Link href="/requests" onClick={() => setMobileOpen(false)}>Baju custom <ArrowUpRight size={16} aria-hidden="true" /></Link>
              <Link href="/designs" onClick={() => setMobileOpen(false)}>Desain tersimpan <ArrowUpRight size={16} aria-hidden="true" /></Link>
              <Link href="/messages" onClick={() => setMobileOpen(false)}>Pesan <ArrowUpRight size={16} aria-hidden="true" /></Link>
              <Link href="/account" onClick={() => setMobileOpen(false)}>Akun saya <ArrowUpRight size={16} aria-hidden="true" /></Link>
              {has("merchant") && <Link href="/merchant" onClick={() => setMobileOpen(false)}>Ruang penjual <ArrowUpRight size={16} aria-hidden="true" /></Link>}
              {has("tailor") && <Link href="/tailor" onClick={() => setMobileOpen(false)}>Ruang penjahit <ArrowUpRight size={16} aria-hidden="true" /></Link>}
              {has("admin") && <Link href="/admin" onClick={() => setMobileOpen(false)}>Ruang admin <ArrowUpRight size={16} aria-hidden="true" /></Link>}
              <button type="button" onClick={() => { logout(); setMobileOpen(false); }}>Keluar</button>
            </>
          ) : (
            <>
              <Link href="/login" onClick={() => setMobileOpen(false)}>Masuk <ArrowUpRight size={16} aria-hidden="true" /></Link>
              <Link href="/register" onClick={() => setMobileOpen(false)}>Daftar <ArrowUpRight size={16} aria-hidden="true" /></Link>
            </>
          )}
        </nav>
      )}
    </header>
  );
}
