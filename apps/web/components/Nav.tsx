"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

export function Nav({ onField = false }: { onField?: boolean }) {
  const { me, ready, logout, has } = useAuth();
  const home = has("admin") ? "/admin" : has("merchant") ? "/merchant" : has("tailor") ? "/tailor" : "/orders";
  return (
    <header className={`frame flex items-center justify-between gap-6 py-5 ${onField ? "on-field" : ""}`}>
      <Link href="/" className="font-display text-2xl font-light tracking-tight no-underline" style={{ fontFamily: "Zodiak, Georgia, serif" }}>
        Tenara
      </Link>
      <nav className="flex items-center gap-5 text-base sm:gap-8" aria-label="Utama">
        <Link href="/gallery" className="no-underline hover:underline underline-offset-4">Gallery</Link>
        {ready && me ? (
          <>
            <Link href={home} className="no-underline hover:underline underline-offset-4">{has("admin") || has("merchant") || has("tailor") ? "Dasbor" : "Pesanan"}</Link>
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
