"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Notice, Page, RequireAuth, useLoad } from "@/components/ui";
import { api, when } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { REQUEST_STATUS } from "@/lib/design";

type Row = { id: string; status: string; submitted_at: string | null; selling_unit?: string; requested_quantity?: string };

function List() {
  const { has } = useAuth();
  const roles = (["buyer", "merchant", "tailor"] as const).filter((r) => has(r));
  const asParam = useSearchParams().get("as");
  const as = roles.find((r) => r === asParam) ?? roles[0] ?? "buyer";
  const { data, error, loading } = useLoad(() => api<{ items: Row[] }>(`/custom-requests?as=${as}`), as);
  return (
    <>
      {roles.length > 1 && (
        <p className="mb-8 flex flex-wrap gap-4 text-base">
          {roles.map((r) => <Link key={r} href={`/requests?as=${r}`} className={r === as ? "link font-medium" : "no-underline hover:underline underline-offset-4"}>{{ buyer: "Sebagai pembeli", merchant: "Sebagai penjual", tailor: "Sebagai penjahit" }[r]}</Link>)}
        </p>
      )}
      {error && <Notice tone="error">{error}</Notice>}
      {loading ? <p>Memuat…</p> : data?.items.length === 0 ? <p>Belum ada permintaan.</p> : (
        <ul className="grid max-w-3xl list-none gap-0 p-0">
          {data?.items.map((r) => (
            <li key={r.id}>
              <Link href={`/requests/${r.id}?as=${as}`} className="group grid grid-cols-[1fr_auto] gap-x-6 py-4 no-underline">
                <span className="text-lg group-hover:underline underline-offset-4">Permintaan baju {r.id.slice(0, 8)}</span>
                <span className="text-base">{REQUEST_STATUS[r.status] ?? r.status}</span>
                <span className="text-base text-muted">{when(r.submitted_at)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

export default function RequestsPage() {
  return (
    <Page>
      <h1 className="t-head mb-10 mt-8">Permintaan baju</h1>
      <RequireAuth><Suspense fallback={null}><List /></Suspense></RequireAuth>
    </Page>
  );
}
