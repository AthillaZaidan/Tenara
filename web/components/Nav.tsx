"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

export function Nav({ onField = false }: { onField?: boolean }) {
  const { me, ready, logout, has } = useAuth();
  return (
    <header className={`frame flex items-center justify-between gap-6 py-5 ${onField ? "on-field" : ""}`}>
      <Link href="/" className="font-display text-2xl font-light tracking-tight no-underline" style={{ fontFamily: "Zodiak, Georgia, serif" }}>
        Tenara
      </Link>
      <nav className="flex flex-wrap items-center justify-end gap-x-5 gap-y-2 text-base sm:gap-x-8" aria-label="Utama">
        <Link href="/gallery" className="no-underline hover:underline underline-offset-4">Gallery</Link>
        {ready && me ? (
          <>
            <Link href="/orders" className="no-underline hover:underline underline-offset-4">Pesanan</Link>
            <Link href="/requests" className="no-underline hover:underline underline-offset-4">Baju custom</Link>
            {has("merchant") && <Link href="/merchant" className="no-underline hover:underline underline-offset-4">Penjual</Link>}
            {has("tailor") && <Link href="/tailor" className="no-underline hover:underline underline-offset-4">Penjahit</Link>}
            {has("admin") && <Link href="/admin" className="no-underline hover:underline underline-offset-4">Admin</Link>}
            <button onClick={logout} className="cursor-pointer hover:underline underline-offset-4">Keluar</button>
          </>
        ) : (
          <>
            <Link href="/login" className="no-underline hover:underline underline-offset-4">Masuk</Link>
            <Link href="/register" className="btn !min-h-10 !px-4 no-underline">Daftar</Link>
          </>
        )}
      </nav>
    </header>
  );
}
