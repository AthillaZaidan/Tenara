"use client";

import Link from "next/link";
import { Page, RequireAuth, useLoad } from "@/components/ui";
import { api } from "@/lib/api";

function Overview() {
  const apps = useLoad(() => api<{ items: { status: string }[] }>("/admin/partner-applications"), "a");
  const appeals = useLoad(() => api<{ items: { status: string }[] }>("/admin/appeals"), "b");
  const entries = useLoad(() => api<{ items: { status: string }[] }>("/admin/gallery?limit=100"), "c");
  const pendingApps = apps.data?.items.filter((a) => ["submitted", "in_review", "information_requested"].includes(a.status)).length ?? 0;
  const openAppeals = appeals.data?.items.filter((a) => a.status !== "decided").length ?? 0;
  const drafts = entries.data?.items.filter((e) => e.status !== "published").length ?? 0;
  const cards: [string, string, string][] = [
    ["/admin/partners", "Pendaftaran mitra", `${pendingApps} menunggu`],
    ["/admin/gallery", "Gallery", `${drafts} belum terbit`],
    ["/admin/appeals", "Banding klaim", `${openAppeals} terbuka`],
    ["/orders?as=admin", "Semua pesanan", "simulasi pengiriman, penyelesaian"],
  ];
  return (
    <ul className="grid max-w-4xl list-none gap-4 p-0 sm:grid-cols-2">
      {cards.map(([href, title, note]) => (
        <li key={href}><Link href={href} className="grid h-full gap-2 bg-surface p-6 no-underline hover:translate-y-[-2px]" style={{ transition: "transform .15s" }}><span className="text-2xl" style={{ fontFamily: "Zodiak, Georgia, serif", fontWeight: 300 }}>{title}</span><span className="text-base text-muted">{note}</span></Link></li>
      ))}
    </ul>
  );
}

export default function AdminPage() {
  return (
    <Page>
      <h1 className="t-head mb-10 mt-8">Dasbor admin</h1>
      <RequireAuth role="admin"><Overview /></RequireAuth>
    </Page>
  );
}
