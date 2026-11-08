"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect } from "react";
import { api, tokens } from "./api";
import { useI18n } from "./i18n";
import type { Me } from "./types";

type AuthCtx = { me: Me | undefined; loading: boolean; can: (perm: string) => boolean; logout: () => Promise<void> };
const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const qc = useQueryClient();
  const router = useRouter();
  const { setLocale, locale } = useI18n();
  const hasToken = typeof window !== "undefined" && !!tokens.access;
  const { data: me, isLoading } = useQuery({ queryKey: ["me"], queryFn: () => api<Me>("/auth/me"), enabled: hasToken, staleTime: 5 * 60_000 });

  useEffect(() => {
    if (typeof window !== "undefined" && !tokens.access) router.replace(`/login?next=${encodeURIComponent(location.pathname)}`);
  }, [router]);

  useEffect(() => {
    // apply a persisted server-side preference only if the user has not chosen locally on this device
    if (me && !localStorage.getItem("rip_locale") && me.preferred_locale !== locale) setLocale(me.preferred_locale);
  }, [me, locale, setLocale]);

  const can = useCallback((perm: string) => !!me?.permissions.includes(perm), [me]);
  const logout = useCallback(async () => {
    try { await api("/auth/logout", { method: "POST" }); } catch { /* token may already be invalid */ }
    tokens.clear();
    qc.clear();
    router.replace("/login");
  }, [qc, router]);

  return <Ctx.Provider value={{ me, loading: isLoading || !hasToken, can, logout }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}
