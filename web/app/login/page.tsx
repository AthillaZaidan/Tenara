"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Field, Notice, Page, useAction } from "@/components/ui";
import { useAuth } from "@/lib/auth";

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const next = useSearchParams().get("next") || "/orders";
  const { busy, error, run } = useAction();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  return (
    <form
      className="grid max-w-md gap-5"
      onSubmit={async (e) => {
        e.preventDefault();
        const user = await run(() => login(email, password));
        if (user) router.replace(next.startsWith("/") ? next : "/orders");
      }}
    >
      <Field label="Email"><input className="field" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
      <Field label="Kata sandi"><input className="field" type="password" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
      {error && <Notice tone="error">{error}</Notice>}
      <button className="btn" disabled={busy}>{busy ? "Masuk…" : "Masuk"}</button>
      <p className="text-base">Belum punya akun? <Link href={`/register?next=${encodeURIComponent(next)}`} className="link">Daftar</Link></p>
    </form>
  );
}

export default function LoginPage() {
  return (
    <Page>
      <h1 className="t-head mb-10 mt-8">Masuk</h1>
      <Suspense fallback={null}><LoginForm /></Suspense>
    </Page>
  );
}
