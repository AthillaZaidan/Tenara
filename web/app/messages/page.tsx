"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { ChevronRight, MessageCircle, Search, X } from "lucide-react";
import { api } from "@/lib/api";
import { RequireAuth, useLoad } from "@/components/ui";
import { useWorkspaceRole, WorkspaceEmpty, WorkspaceError, WorkspaceLoading, WorkspaceRoute } from "@/components/PartnerWorkspace";

type Conversation = { id: string; subject: string; kind: string; members: { user_id: string; role: string }[]; viewer_id: string };

function Inbox() {
  const inbox = useLoad(() => api<Conversation[]>("/conversations"), "inbox");
  const role = useWorkspaceRole();
  const [search, setSearch] = useState("");
  const roles: Record<string, string> = { merchant: "Penjual", tailor: "Penjahit", buyer: "Pembeli", reviewer: "Peninjau" };
  const items = (inbox.data ?? []).filter((conversation) => role !== "merchant" && role !== "tailor" || conversation.members.some((member) => member.user_id === conversation.viewer_id && member.role === role));
  const visible = items.filter((conversation) => conversation.subject.toLocaleLowerCase("id").includes(search.trim().toLocaleLowerCase("id")));
  return <section className="workspace-panel">
    <div className="sectionHeading"><div><h2>Percakapan Anda</h2><p>Semua diskusi tentang pesanan dan rancangan, dalam satu tempat.</p></div><span className="count">{inbox.data ? `${items.length} percakapan` : "—"}</span></div>
    <div className="toolbar"><label className="search"><Search size={16} /><input aria-label="Cari percakapan" placeholder="Cari percakapan…" value={search} onChange={(e) => setSearch(e.target.value)} />{search && <button type="button" aria-label="Hapus pencarian" onClick={() => setSearch("")}><X size={14} /></button>}</label></div>
    {inbox.error ? <WorkspaceError message={inbox.error} retry={inbox.reload} /> : inbox.loading ? <WorkspaceLoading>Memuat percakapan…</WorkspaceLoading> : visible.length === 0 ? <WorkspaceEmpty icon={MessageCircle} title={search ? "Percakapan belum ditemukan" : "Percakapan baik, karya lebih berarti"} description={search ? "Coba kata kunci lain untuk menemukan diskusi Anda." : "Mulai diskusi dengan pembeli dari halaman pesanan atau permintaan baju. Percakapannya akan tersimpan di sini."} {...(search ? { onReset: () => setSearch("") } : { href: `/orders?as=${role}`, action: "Lihat pesanan" })} /> : <ul className="workspace-conversations">{visible.map((conversation) => <li key={conversation.id}><Link href={`/messages/${conversation.id}?as=${role}`}><span className="workspace-message-icon"><MessageCircle size={21} strokeWidth={1.3} /></span><span><strong>{conversation.subject}</strong><small>{conversation.members.filter((m) => m.user_id !== conversation.viewer_id).map((m) => roles[m.role] ?? m.role).join(", ")}</small></span><ChevronRight size={16} /></Link></li>)}</ul>}
  </section>;
}

export default function MessagesPage() { return <Suspense fallback={<WorkspaceLoading />}><RequireAuth><WorkspaceRoute active="messages" title="Pesan" description="Jaga komunikasi yang baik di setiap langkah berkarya."><Inbox /></WorkspaceRoute></RequireAuth></Suspense>; }
