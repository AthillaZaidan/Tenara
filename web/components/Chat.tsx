"use client";

import { useEffect, useRef, useState } from "react";
import { api, when } from "@/lib/api";
import { errText, Notice, useAction } from "./ui";

type Message = { id: string; sender_id: string; body: string; created_at: string };

export function Chat({ conversationId, viewerId }: { conversationId: string; viewerId: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const act = useAction();
  const end = useRef<HTMLLIElement>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let alive = true;
    const pull = async () => {
      try {
        const res = await api<{ items: Message[] }>(`/conversations/${conversationId}/messages`);
        if (alive) { setMessages(res.items); setLoadError(null); }
      } catch (error) {
        if (alive) setLoadError(errText(error));
      } finally {
        if (alive) setLoading(false);
      }
    };
    pull();
    const t = setInterval(pull, 5000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [conversationId, version]);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest" });
  }, [messages.length]);

  return (
    <div className="chat grid max-w-2xl gap-4">
      {loadError && <div className="grid gap-2 p-4"><Notice tone="error">{loadError}</Notice><button type="button" className="link w-fit text-sm" onClick={() => setVersion((value) => value + 1)}>Coba lagi</button></div>}
      <ul className="chat-messages grid max-h-[28rem] list-none gap-3 overflow-y-auto bg-surface p-4" aria-live="polite" aria-label="Percakapan" aria-busy={loading}>
        {messages.length === 0 && <li className="chat-empty text-base text-muted">{loading ? "Memuat pesan…" : loadError ? "Pesan belum dapat dimuat." : "Belum ada pesan. Mulai percakapan Anda di sini."}</li>}
        {messages.map((m) => (
          <li key={m.id} className={`chat-message grid max-w-[85%] gap-1 p-3 ${m.sender_id === viewerId ? "chat-message--own ml-auto bg-field text-field-ink" : "bg-bg"}`}>
            <span className="whitespace-pre-wrap">{m.body}</span>
            <span className="t-small opacity-80">{when(m.created_at)}</span>
          </li>
        ))}
        <li ref={end} aria-hidden="true" />
      </ul>
      {act.error && <Notice tone="error">{act.error}</Notice>}
      <form
        className="chat-compose flex gap-3"
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
      <p className="chat-note t-small text-muted">Percakapan tersimpan bersama pesanan Anda. Admin dapat melihat percakapan klaim.</p>
    </div>
  );
}
