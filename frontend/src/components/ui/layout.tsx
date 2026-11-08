"use client";

import * as T from "@radix-ui/react-tabs";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function PageHeader({ title, subtitle, actions, crumbs, meta }: {
  title: string; subtitle?: string; actions?: React.ReactNode; crumbs?: { label: string; href?: string }[]; meta?: React.ReactNode;
}) {
  const { dir } = useI18n();
  const Sep = dir === "rtl" ? ChevronLeft : ChevronRight;
  return (
    <header className="mb-7">
      {crumbs && (
        <nav aria-label="breadcrumb" className="mb-3">
          <ol className="flex flex-wrap items-center gap-1 text-[12.5px] text-muted">
            {crumbs.map((c, i) => (
              <li key={i} className="flex items-center gap-1">
                {c.href ? <Link className="hover:text-ink" href={c.href}>{c.label}</Link> : <span aria-current="page" className="text-ink-2">{c.label}</span>}
                {i < crumbs.length - 1 && <Sep className="size-3.5" aria-hidden />}
              </li>
            ))}
          </ol>
        </nav>
      )}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[24px] font-semibold leading-tight tracking-[-0.01em] text-ink">{title}</h1>
          {subtitle && <p className="mt-1.5 max-w-2xl text-[13.5px] text-muted">{subtitle}</p>}
          {meta && <div className="mt-3 flex flex-wrap items-center gap-2">{meta}</div>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  );
}

export function Panel({ title, description, actions, children, className, bodyClass, id }: {
  title?: React.ReactNode; description?: string; actions?: React.ReactNode; children: React.ReactNode; className?: string; bodyClass?: string; id?: string;
}) {
  return (
    <section id={id} className={cn("rounded-xl border border-line bg-surface", className)}>
      {(title || actions) && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5">
          <div>
            {title && <h2 className="text-[14.5px] font-semibold text-ink">{title}</h2>}
            {description && <p className="mt-0.5 text-[12.5px] text-muted">{description}</p>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </div>
      )}
      <div className={cn("p-5", bodyClass)}>{children}</div>
    </section>
  );
}

export function Tabs({ value, onValueChange, items, children, className }: {
  value: string; onValueChange: (v: string) => void; items: { value: string; label: string; count?: number }[]; children: React.ReactNode; className?: string;
}) {
  const { dir } = useI18n();
  return (
    <T.Root value={value} onValueChange={onValueChange} dir={dir} className={className}>
      <T.List className="mb-5 flex gap-5 overflow-x-auto border-b border-line scroll-thin">
        {items.map((i) => (
          <T.Trigger key={i.value} value={i.value}
            className="relative -mb-px flex items-center gap-2 whitespace-nowrap border-b-2 border-transparent pb-2.5 pt-1 text-[13.5px] font-medium text-muted transition-colors hover:text-ink data-[state=active]:border-primary data-[state=active]:text-ink">
            {i.label}
            {i.count !== undefined && <span className="rounded-full bg-surface-2 px-1.5 text-[11.5px] text-muted num">{i.count}</span>}
          </T.Trigger>
        ))}
      </T.List>
      {children}
    </T.Root>
  );
}
export const TabPanel = T.Content;

export function DescList({ items, cols = 2 }: { items: { label: string; value: React.ReactNode }[]; cols?: 1 | 2 | 3 }) {
  return (
    <dl className={cn("grid gap-x-8 gap-y-4", cols === 1 ? "grid-cols-1" : cols === 2 ? "sm:grid-cols-2" : "sm:grid-cols-3")}>
      {items.map((it, i) => (
        <div key={i} className="min-w-0">
          <dt className="text-[12.5px] text-muted">{it.label}</dt>
          <dd className="mt-0.5 break-words text-[13.5px] text-ink">{it.value || <span className="text-faint">—</span>}</dd>
        </div>
      ))}
    </dl>
  );
}
