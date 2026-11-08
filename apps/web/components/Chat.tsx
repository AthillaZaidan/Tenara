"use client";

import { useEffect, useRef, useState } from "react";
import { api, when } from "@/lib/api";
import { Notice, useAction } from "./ui";

type Message = { id: string; sender_id: string; body: string; created_at: string };

export function Chat({ conversationId, viewerId }: { conversationId: string; viewerId: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const act = useAction();
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    const pull = async () => {
      try {
        const res = await api<{ items: Message[] }>(`/conversations/${conversationId}/messages`);
        if (alive) setMessages(res.items);
      } catch {
        /* keep the last good list; the next poll retries */
      }
    };
    pull();
    const t = setInterval(pull, 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [conversationId]);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [messages.length]);

  return (
    <div className="grid max-w-2xl gap-4">
      <ul className="grid max-h-[28rem] list-none gap-3 overflow-y-auto bg-surface p-4" aria-live="polite" aria-label="Percakapan">
        {messages.length === 0 && <li className="text-base text-muted">Belum ada pesan.</li>}
        {messages.map((m) => (
          <li key={m.id} className={`grid max-w-[85%] gap-1 p-3 ${m.sender_id === viewerId ? "ml-auto bg-field text-field-ink" : "bg-bg"}`}>
            <span className="whitespace-pre-wrap">{m.body}</span>
            <span className="t-small opacity-80">{when(m.created_at)}</span>
          </li>
        ))}
        <div ref={end} />
      </ul>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <form
        className="flex gap-3"
        onSubmit={async (e) => {
          e.preventDefault();
          const body = text.trim();
          if (!body) return;
          const sent = await act.run(() => api<Message>(`/conversations/${conversationId}/messages`, { body: { body } }));
          if (sent) {
            setText("");
            setMessages((prev) => [...prev, sent]);
          }
        }}
      >
        <input className="field" value={text} onChange={(e) => setText(e.target.value)} placeholder="Tulis pesan" aria-label="Pesan" maxLength={2000} />
        <button className="btn" disabled={act.busy || !text.trim()}>Kirim</button>
      </form>
      <p className="t-small text-muted">Jangan membagikan data pribadi di luar yang perlu untuk pesanan. Admin dapat melihat percakapan klaim.</p>
    </div>
  );
}
