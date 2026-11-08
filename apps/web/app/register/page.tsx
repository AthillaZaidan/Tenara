"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Field, Notice, Page, useAction } from "@/components/ui";
import { useAuth } from "@/lib/auth";

function RegisterForm() {
  const { register } = useAuth();
  const router = useRouter();
  const next = useSearchParams().get("next") || "/orders";
  const { busy, error, run } = useAction();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  return (
    <form
      className="grid max-w-md gap-5"
      onSubmit={async (e) => {
        e.preventDefault();
        const user = await run(() => register(email, password, name));
        if (user) router.replace(next.startsWith("/") ? next : "/orders");
      }}
    >
      <Field label="Nama"><input className="field" required autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="Email"><input className="field" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
      <Field label="Kata sandi" hint="Minimal 8 karakter."><input className="field" type="password" required minLength={8} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
      {error && <Notice tone="error">{error}</Notice>}
      <button className="btn" disabled={busy}>{busy ? "Mendaftar…" : "Buat akun"}</button>
      <p className="text-base">Sudah punya akun? <Link href={`/login?next=${encodeURIComponent(next)}`} className="link">Masuk</Link></p>
    </form>
  );
}

export default function RegisterPage() {
  return (
    <Page>
      <h1 className="t-head mb-10 mt-8">Buat akun</h1>
      <Suspense fallback={null}><RegisterForm /></Suspense>
    </Page>
  );
}
