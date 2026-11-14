"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Suspense } from "react";
import { ArrowUpRight } from "lucide-react";
import { Chat } from "@/components/Chat";
import { RequireAuth, useLoad } from "@/components/ui";
import { useWorkspaceRole, WorkspaceError, WorkspaceLoading, WorkspaceRoute } from "@/components/PartnerWorkspace";
import { api } from "@/lib/api";

type Conversation = { id: string; subject: string; viewer_id: string; order_id: string | null; request_id: string | null };

function ConversationView() {
  const { id } = useParams<{ id: string }>();
  const role = useWorkspaceRole();
  const conversations = useLoad(() => api<Conversation[]>("/conversations"), id);
  const conversation = conversations.data?.find((item) => item.id === id);
  if (conversations.loading) return <WorkspaceLoading>Memuat percakapan…</WorkspaceLoading>;
  if (conversations.error || !conversation) return <WorkspaceError message={conversations.error ?? "Percakapan tidak ditemukan."} retry={conversations.reload} />;
  return <section className="workspace-panel"><div className="workspace-chat-header"><h2>{conversation.subject}</h2>
    {conversation.order_id && <Link href={`/orders/${conversation.order_id}?as=${role}`} className="workspace-link">Lihat pesanan<ArrowUpRight size={14} /></Link>}
    {conversation.request_id && <Link href={`/requests/${conversation.request_id}?as=${role}`} className="workspace-link">Lihat permintaan<ArrowUpRight size={14} /></Link>}</div>
    <Chat conversationId={conversation.id} viewerId={conversation.viewer_id} />
  </section>;
}

export default function ConversationPage() { return <Suspense fallback={<WorkspaceLoading />}><RequireAuth><WorkspaceRoute active="messages" title="Percakapan" description="Diskusikan detail dan perkembangan karya bersama pembeli." back={{ href: "/messages", label: "Pesan" }}><ConversationView /></WorkspaceRoute></RequireAuth></Suspense>; }
