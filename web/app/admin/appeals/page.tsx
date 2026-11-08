"use client";

import Link from "next/link";
import { Notice, Page, RequireAuth, useLoad } from "@/components/ui";
import { api, when } from "@/lib/api";

type Row = { id: string; status: string; basis: string; claim_id: string; component: string; target_role: string; reason: string; created_at: string };

function List() {
  const { data, error, loading } = useLoad(() => api<{ items: Row[] }>("/admin/appeals"), "ap");
  return (
    <>
      {error && <Notice tone="error">{error}</Notice>}
      {loading ? <p>Memuat…</p> : data?.items.length === 0 ? <p>Tidak ada banding.</p> : (
        <ul className="grid max-w-3xl list-none gap-0 p-0">
          {data?.items.map((a) => (
            <li key={a.id}><Link href={`/admin/appeals/${a.id}`} className="group grid grid-cols-[1fr_auto] gap-x-6 py-4 no-underline"><span className="text-lg group-hover:underline underline-offset-4">Klaim {a.component} terhadap {a.target_role === "tailor" ? "penjahit" : "penjual"}</span><span className="text-base">{a.status.replaceAll("_", " ")}</span><span className="text-base text-muted">{a.basis === "no_response" ? "Mitra tidak menanggapi" : "Penolakan mitra"} · {when(a.created_at)}</span></Link></li>
          ))}
        </ul>
      )}
    </>
  );
}

export default function AdminAppealsPage() {
  return (
    <Page>
      <p className="mb-2 mt-6 text-base"><Link href="/admin" className="link">← Admin</Link></p>
      <h1 className="t-head mb-10">Banding klaim</h1>
      <RequireAuth role="admin"><List /></RequireAuth>
    </Page>
  );
}
