"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Chat } from "@/components/Chat";
import { Notice, Page, RequireAuth, useAction, useLoad } from "@/components/ui";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Conv = { id: string; kind: string; subject: string; order_id: string | null; members: { user_id: string; role: string }[]; viewer_id: string };

function View() {
  const { id } = useParams<{ id: string }>();
  const { me, has } = useAuth();
  const { data, error, reload } = useLoad(() => api<Conv[]>("/conversations"), id);
  const order = useLoad(() => api<{ kind: string }>(`/orders/${id}`), id);
  const act = useAction();
  const [active, setActive] = useState<string | null>(null);
  const mine = (data ?? []).filter((c) => c.order_id === id && c.kind !== "claim");
  const current = active ?? mine[0]?.id ?? null;
  const label = (c: Conv) => c.members.filter((m) => m.user_id !== me?.id).map((m) => ({ merchant: "Penjual", tailor: "Penjahit", buyer: "Pembeli", reviewer: "Reviewer" }[m.role] ?? m.role)).join(", ");
  const open = async (who: "merchant" | "tailor") => {
    const c = await act.run(() => api<Conv>("/conversations", { body: { order_id: id, with: who } }));
    if (c) {
      setActive(c.id);
      reload();
    }
  };
  return (
    <div className="grid gap-8">
      {error && <Notice tone="error">{error}</Notice>}
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <div className="flex flex-wrap gap-3">
        {mine.map((c) => (
          <button key={c.id} className={c.id === current ? "btn" : "btn btn-quiet"} onClick={() => setActive(c.id)}>{label(c) || c.subject}</button>
        ))}
        {has("buyer") && !mine.some((c) => label(c).includes("Penjual")) && <button className="btn btn-quiet" onClick={() => open("merchant")} disabled={act.busy}>Mulai chat dengan penjual</button>}
        {has("buyer") && order.data?.kind === "custom" && !mine.some((c) => label(c).includes("Penjahit")) && <button className="btn btn-quiet" onClick={() => open("tailor")} disabled={act.busy}>Mulai chat dengan penjahit</button>}
      </div>
      {current && me ? <Chat key={current} conversationId={current} viewerId={me.id} /> : <p>Belum ada percakapan untuk pesanan ini.</p>}
    </div>
  );
}

export default function ChatPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <Page>
      <p className="mb-2 mt-6 text-base"><Link href={`/orders/${id}`} className="link">← Pesanan</Link></p>
      <h1 className="t-head mb-8">Pesan</h1>
      <RequireAuth><View /></RequireAuth>
    </Page>
  );
}
