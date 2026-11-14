"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Footer } from "./Footer";
import { Nav } from "./Nav";

export function Page({ children, narrow = false }: { children: React.ReactNode; narrow?: boolean }) {
  return (
    <>
      <Nav />
      <main className={`frame pb-[clamp(72px,10vw,140px)] pt-6 ${narrow ? "mx-auto max-w-3xl" : ""}`}>{children}</main>
      <Footer />
    </>
  );
}

export function Notice({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "error" }) {
  return (
    <p role={tone === "error" ? "alert" : "status"} className={`p-4 text-base ${tone === "error" ? "bg-field text-field-ink" : "bg-surface"}`}>
      {children}
    </p>
  );
}

export const errText = (e: unknown) => (e instanceof ApiError ? e.message : "Terjadi kesalahan. Coba lagi.");

/** Loads data when `key` changes (and again after reload()), exposing loading and error states. */
export function useLoad<T>(fn: () => Promise<T>, key: string = "") {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    let alive = true;
    fn()
      .then((d) => {
        if (!alive) return;
        setData(d);
        setError(null);
      })
      .catch((e) => alive && setError(errText(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // fn is recreated each render by design; `key` and `version` decide when to refetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, version]);
  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { data, error, loading, reload, setData };
}

/** Wraps a mutating call: tracks busy and error, returns the result (or undefined on failure). */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(errText(e));
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);
  return { busy, error, run, setError };
}

/** Sends visitors without a session to /login and back; optionally requires a role. */
export function RequireAuth({ role, children, loadingFallback }: { role?: string; children: React.ReactNode; loadingFallback?: React.ReactNode }) {
  const { me, ready, has } = useAuth();
  const router = useRouter();
  const path = usePathname();
  useEffect(() => {
    if (ready && !me) router.replace(`/login?next=${encodeURIComponent(path)}`);
  }, [ready, me, router, path]);
  if (!ready || !me) return loadingFallback ?? <p className="py-24">Memuat…</p>;
  if (role && !has(role)) {
    return (
      <div className="grid gap-4 py-16">
        <h1 className="t-head">Halaman ini untuk {role === "admin" ? "admin" : role === "merchant" ? "penjual kain" : "penjahit"}</h1>
        <p>Akun Anda belum memiliki peran tersebut.</p>
        <Link href="/partner" className="btn w-fit no-underline">Ajukan sebagai mitra</Link>
      </div>
    );
  }
  return <>{children}</>;
}

export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="grid gap-2 text-base">
      <span>{label}</span>
      {children}
      {hint && <span className="t-small text-muted">{hint}</span>}
    </label>
  );
}

export function Status({ value }: { value: string }) {
  const labels: Record<string, string> = {
    confirmed: "Dikonfirmasi", preparing: "Disiapkan", shipped: "Dikirim", delivered: "Tiba", completed: "Selesai",
    cancelled: "Dibatalkan", draft: "Draf", submitted: "Diajukan", published: "Terbit", pending: "Menunggu",
  };
  return <span className="bg-surface px-2 py-1 text-base">{labels[value] ?? value.replaceAll("_", " ")}</span>;
}
