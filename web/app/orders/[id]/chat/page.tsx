"use client";

import { useParams } from "next/navigation";
import { Suspense, useState } from "react";
import { MessageCircle } from "lucide-react";
import { Chat } from "@/components/Chat";
import { Notice, RequireAuth, useAction, useLoad } from "@/components/ui";
import { useWorkspaceRole, WorkspaceEmpty, WorkspaceError, WorkspaceLoading, WorkspaceRoute } from "@/components/PartnerWorkspace";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Conv = { id: string; kind: string; subject: string; order_id: string | null; members: { user_id: string; role: string }[]; viewer_id: string };

function View() {
  const { id } = useParams<{ id: string }>();
  const { me } = useAuth();
  const role = useWorkspaceRole();
  const { data, error, loading, reload } = useLoad(() => api<Conv[]>("/conversations"), id);
  const order = useLoad(() => api<{ kind: string }>(`/orders/${id}`), id);
  const act = useAction();
  const [active, setActive] = useState<string | null>(null);
  const mine = (data ?? []).filter((c) => c.order_id === id && c.kind !== "claim" && (role !== "merchant" && role !== "tailor" || c.members.some((member) => member.user_id === me?.id && member.role === role)));
  const current = active ?? mine[0]?.id ?? null;
  const label = (c: Conv) => c.members.filter((m) => m.user_id !== me?.id).map((m) => ({ merchant: "Penjual", tailor: "Penjahit", buyer: "Pembeli", reviewer: "Reviewer" }[m.role] ?? m.role)).join(", ");
  const open = async (who: "merchant" | "tailor") => {
    const c = await act.run(() => api<Conv>("/conversations", { body: { order_id: id, with: who } }));
    if (c) {
      setActive(c.id);
      reload();
    }
  };
  if (loading) return <WorkspaceLoading>Memuat percakapan…</WorkspaceLoading>;
  if (error) return <WorkspaceError message={error} retry={reload} />;
  return (
    <div className="workspace-stack">
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <div className="workspace-chat-tabs flex flex-wrap gap-3">
        {mine.map((c) => (
          <button key={c.id} className={c.id === current ? "btn" : "btn btn-quiet"} onClick={() => setActive(c.id)}>{label(c) || c.subject}</button>
        ))}
        {role === "buyer" && !mine.some((c) => label(c).includes("Penjual")) && <button className="btn btn-quiet" onClick={() => open("merchant")} disabled={act.busy}>Mulai chat dengan penjual</button>}
        {role === "buyer" && order.data?.kind === "custom" && !mine.some((c) => label(c).includes("Penjahit")) && <button className="btn btn-quiet" onClick={() => open("tailor")} disabled={act.busy}>Mulai chat dengan penjahit</button>}
        {(role === "merchant" || role === "tailor") && !mine.length && <button className="btn" onClick={() => open(role)} disabled={act.busy}><MessageCircle size={15} />{act.busy ? "Menyiapkan percakapan…" : "Mulai chat dengan pembeli"}</button>}
      </div>
      <section className="workspace-panel">{current && me ? <Chat key={current} conversationId={current} viewerId={me.id} /> : <WorkspaceEmpty icon={MessageCircle} title="Ruang untuk saling memahami" description="Tanyakan detail atau bagikan perkembangan pesanan. Percakapan Anda akan tampil di sini." />}</section>
    </div>
  );
}

export default function ChatPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <Suspense fallback={<WorkspaceLoading />}><RequireAuth><WorkspaceRoute active="orders" title="Percakapan pesanan" description="Satu tempat untuk mendiskusikan setiap detail pesanan." back={{ href: `/orders/${id}`, label: "Detail pesanan" }}><View /></WorkspaceRoute></RequireAuth></Suspense>
  );
}
