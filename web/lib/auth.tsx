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
  refresh: () => Promise<Me | null>;
  has: (role: string) => boolean;
};

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [ready, setReady] = useState(false);

  const load = useCallback(async (): Promise<Me | null> => {
    if (!tokenStore.get()) return null;
    try {
      return await api<Me>("/auth/me");
    } catch {
      tokenStore.set(null);
      return null;
    }
  }, []);

  useEffect(() => {
    let alive = true;
    load().then((data) => {
      if (!alive) return;
      setMe(data);
      setReady(true);
    });
    return () => {
      alive = false;
    };
  }, [load]);

  const value = useMemo<AuthState>(() => {
    const login = async (email: string, password: string): Promise<Me> => {
      const res = await api<{ access_token: string }>("/auth/login", { body: { email, password }, token: null });
      tokenStore.set(res.access_token);
      const user = await load();
      setMe(user);
      return user!;
    };
    return {
      me,
      ready,
      login,
      async register(email: string, password: string, displayName: string): Promise<Me> {
        await api("/auth/register", { body: { email, password, display_name: displayName }, token: null });
        return login(email, password);
      },
      logout() {
        tokenStore.set(null);
        setMe(null);
      },
      async refresh() {
        const user = await load();
        setMe(user);
        return user;
      },
      has: (role: string) => !!me?.roles.some((r) => r.role === role && r.status === "active"),
    };
  }, [me, ready, load]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
