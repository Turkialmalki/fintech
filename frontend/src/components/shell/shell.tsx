"use client";

import * as DM from "@radix-ui/react-dropdown-menu";
import * as D from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { Languages, LogOut, Menu, Search, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { Button } from "../ui/button";
import { Logo } from "./logo";
import { NAV } from "./nav";

type SystemInfo = { ai_mock: boolean; embedding_mock: boolean; ai_provider: string; ai_model: string; vector_backend: string };

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useI18n();
  const { can } = useAuth();
  const path = usePathname();
  return (
    <nav aria-label="main" className="flex flex-col gap-6">
      {NAV.map((g) => {
        const items = g.items.filter((i) => !i.perm || can(i.perm));
        if (!items.length) return null;
        return (
          <div key={g.group}>
            <p className="mb-1.5 px-3 text-[11.5px] font-medium text-faint">{t.nav[g.group]}</p>
            <ul className="flex flex-col gap-0.5">
              {items.map((i) => {
                const active = i.href === "/" ? path === "/" : path.startsWith(i.href);
                return (
                  <li key={i.href}>
                    <Link href={i.href} onClick={onNavigate} aria-current={active ? "page" : undefined}
                      className={cn("relative flex items-center gap-3 rounded-md px-3 py-[7px] text-[13.5px] transition-colors",
                        active ? "bg-primary-soft/70 font-medium text-ink" : "text-ink-2 hover:bg-surface-2 hover:text-ink")}>
                      {active && <span className="absolute inset-y-1.5 start-0 w-[3px] rounded-full bg-primary" aria-hidden />}
                      <i.icon className={cn("size-[17px]", active ? "text-primary" : "text-muted")} aria-hidden />
                      {t.nav[i.key]}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

function LanguageSwitch({ compact }: { compact?: boolean }) {
  const { t, locale, setLocale } = useI18n();
  const toggle = () => {
    const next = locale === "ar" ? "en" : "ar";
    setLocale(next);
    api("/auth/me/preferences", { method: "PATCH", body: { preferred_locale: next } }).catch(() => undefined);
  };
  return (
    <Button variant="ghost" size={compact ? "icon" : "sm"} onClick={toggle} aria-label={t.common.language} lang={locale === "ar" ? "en" : "ar"}>
      <Languages />{!compact && <span>{t.common.language}</span>}
    </Button>
  );
}

function UserMenu() {
  const { me, logout } = useAuth();
  const { t, pick, label, dir } = useI18n();
  if (!me) return <div className="skeleton size-8 rounded-full" />;
  const name = pick(me.full_name_ar, me.full_name_en);
  const initials = name.split(" ").map((p) => p[0]).slice(0, 2).join("");
  return (
    <DM.Root dir={dir}>
      <DM.Trigger asChild>
        <button className="flex items-center gap-2.5 rounded-md p-1 pe-2 hover:bg-surface-2" aria-label={name}>
          <span className="grid size-8 place-items-center rounded-full bg-ink text-[12px] font-semibold text-white">{initials}</span>
          <span className="hidden text-start leading-tight md:block">
            <span className="block text-[13px] font-medium">{name}</span>
            <span className="block text-[11.5px] text-muted">{me.role_codes.map((r) => label("role", r)).join("، ")}</span>
          </span>
        </button>
      </DM.Trigger>
      <DM.Portal>
        <DM.Content align="end" sideOffset={6} className="z-50 min-w-56 rounded-lg border border-line bg-surface p-1 shadow-pop">
          <div className="px-3 py-2">
            <p className="text-[13px] font-medium">{name}</p>
            <p className="ltr text-[12px] text-muted">{me.email}</p>
            <p className="mt-1 text-[12px] text-muted">{pick(me.organization.name_ar, me.organization.name_en)}</p>
          </div>
          <DM.Separator className="my-1 h-px bg-line" />
          <DM.Item asChild><Link href="/settings" className="flex rounded-md px-3 py-2 text-[13px] outline-none data-[highlighted]:bg-surface-2">{t.nav.settings}</Link></DM.Item>
          <DM.Item onSelect={() => logout()} className="flex items-center gap-2 rounded-md px-3 py-2 text-[13px] text-danger outline-none data-[highlighted]:bg-danger-soft">
            <LogOut className="size-4" />{t.common.logout}
          </DM.Item>
        </DM.Content>
      </DM.Portal>
    </DM.Root>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { t, pick } = useI18n();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [q, setQ] = useState("");
  const { data: sys } = useQuery({ queryKey: ["system"], queryFn: () => api<SystemInfo>("/system/info"), staleTime: 60_000 });

  return (
    <div className="min-h-dvh">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:start-3 focus:top-3 focus:z-[60] focus:rounded-md focus:bg-ink focus:px-3 focus:py-2 focus:text-white">
        {pick("تخطَّ إلى المحتوى", "Skip to content")}
      </a>
      {/* Desktop sidebar on the inline-start edge (right in Arabic) */}
      <aside className="fixed inset-y-0 start-0 z-30 hidden w-[248px] flex-col border-e border-line bg-surface lg:flex">
        <div className="flex h-16 items-center px-5"><Logo /></div>
        <div className="flex-1 overflow-y-auto scroll-thin px-3 pb-6 pt-2"><NavList /></div>
        <div className="border-t border-line px-5 py-3.5">
          <a href="/readiness" className="flex items-center gap-2 rounded-md px-2 py-1.5 text-[13px] font-medium text-primary hover:bg-primary-soft/50">
            <span className="size-1.5 rounded-full bg-primary" aria-hidden />{pick("فحص الجاهزية العام", "Public readiness check")}
          </a>
        </div>
      </aside>

      <div className="lg:ps-[248px]">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-line bg-surface/85 px-4 backdrop-blur-md md:px-8">
          <D.Root open={mobileOpen} onOpenChange={setMobileOpen}>
            <D.Trigger asChild><Button variant="ghost" size="icon" className="lg:hidden" aria-label="menu"><Menu /></Button></D.Trigger>
            <D.Portal>
              <D.Overlay className="fixed inset-0 z-40 bg-ink/25 lg:hidden" />
              <D.Content className="fixed inset-y-0 start-0 z-50 flex w-[280px] flex-col bg-surface shadow-pop lg:hidden">
                <D.Title className="sr-only">{t.brand.name}</D.Title>
                <div className="flex h-16 items-center justify-between px-5">
                  <Logo />
                  <D.Close asChild><Button variant="ghost" size="icon-sm" aria-label={t.common.close}><X /></Button></D.Close>
                </div>
                <div className="flex-1 overflow-y-auto px-3 pb-6"><NavList onNavigate={() => setMobileOpen(false)} /></div>
              </D.Content>
            </D.Portal>
          </D.Root>
          <div className="lg:hidden"><Logo compact /></div>

          <form role="search" className="relative hidden max-w-md flex-1 md:block"
            onSubmit={(e) => { e.preventDefault(); if (q.trim()) router.push(`/intelligence?q=${encodeURIComponent(q.trim())}`); }}>
            <Search className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={pick("ابحث في الوثائق التنظيمية…", "Search regulatory documents…")}
              aria-label={t.common.search}
              className="h-9 w-full rounded-md border border-line bg-canvas ps-9 pe-3 text-[13.5px] placeholder:text-faint focus:border-primary focus:bg-surface focus:outline-none focus:ring-[3px] focus:ring-primary/15" />
          </form>

          <div className="ms-auto flex items-center gap-1.5">
            {sys?.ai_mock && (
              <span title={t.demo.mockHint} className="hidden items-center gap-1.5 rounded-full border border-line bg-canvas px-2.5 py-0.5 text-[12px] font-medium text-ink-2 sm:inline-flex">
                <span className="size-1.5 rounded-full bg-success" aria-hidden />{t.demo.mock}
              </span>
            )}
            <LanguageSwitch />
            <UserMenu />
          </div>
        </header>
        <main id="main" className="mx-auto w-full max-w-[1400px] px-4 py-7 md:px-8 md:py-9">{children}</main>
      </div>
    </div>
  );
}
