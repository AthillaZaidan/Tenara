"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, tokenStore } from "./api";

export type Me = {
  id: string;
  email: string;
  display_name: string;
  roles: { role: string; status: string }[];
};

type AuthState = {
  me: Me | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<Me>;
  register: (email: string, password: string, displayName: string) => Promise<Me>;
  logout: () => void;
  has: (role: string) => boolean;
};

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);

  const load = useCallback(async () => {
    if (!tokenStore.get()) return null;
    try {
      const data = await api<Me>("/auth/me");
      setMe(data);
      return data;
    } catch {
      tokenStore.set(null);
      setMe(null);
      return null;
    }
  }, []);

  useEffect(() => {
    load().finally(() => setReady(true));
  }, [load]);

  const value = useMemo<AuthState>(
    () => ({
      me,
      ready,
      async login(email, password) {
        const res = await api<{ access_token: string }>("/auth/login", { body: { email, password }, token: null });
        tokenStore.set(res.access_token);
        return (await load())!;
      },
      async register(email, password, displayName) {
        await api("/auth/register", { body: { email, password, display_name: displayName }, token: null });
        return value.login(email, password);
      },
      logout() {
        tokenStore.set(null);
        setMe(null);
      },
      has: (role) => !!me?.roles.some((r) => r.role === role && r.status === "active"),
    }),
    [me, ready, load],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
