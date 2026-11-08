"use client";

import Link from "next/link";
import { Notice, Page, RequireAuth, useLoad } from "@/components/ui";
import { api, when } from "@/lib/api";

type Row = { id: string; order_id: string; status: string; component: string; target_role: string; created_at: string };

function List() {
  const { data, error, loading } = useLoad(() => api<{ items: Row[] }>("/claims"));
  return (
    <>
      {error && <Notice tone="error">{error}</Notice>}
      {loading ? <p>Memuat…</p> : data?.items.length === 0 ? <p>Tidak ada klaim.</p> : (
        <ul className="grid max-w-3xl list-none gap-0 p-0">
          {data?.items.map((c) => (
            <li key={c.id}>
              <Link href={`/claims/${c.id}`} className="group grid grid-cols-[1fr_auto] gap-x-6 py-4 no-underline">
                <span className="text-lg group-hover:underline underline-offset-4">Klaim {c.component} terhadap {c.target_role === "tailor" ? "penjahit" : "penjual"}</span>
                <span className="text-base">{c.status.replaceAll("_", " ")}</span>
                <span className="text-base text-muted">{when(c.created_at)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

export default function ClaimsPage() {
  return (
    <Page>
      <h1 className="t-head mb-10 mt-8">Klaim</h1>
      <RequireAuth><List /></RequireAuth>
    </Page>
  );
}
