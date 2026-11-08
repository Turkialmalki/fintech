"use client";

import { AlertCircle, ShieldAlert } from "lucide-react";
import { ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { Button } from "./button";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton h-4", className)} aria-hidden />;
}

export function SkeletonRows({ rows = 5, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-3", className)} role="status" aria-live="polite">
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className={cn("h-10", i % 3 === 2 && "w-4/5")} />)}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, hint, action, className }: {
  icon?: React.ElementType; title: string; hint?: string; action?: React.ReactNode; className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center gap-2 px-6 py-14 text-center", className)}>
      {Icon && <div className="mb-2 grid size-11 place-items-center rounded-full bg-surface-2 text-muted"><Icon className="size-5" aria-hidden /></div>}
      <p className="text-[15px] font-medium text-ink">{title}</p>
      {hint && <p className="max-w-sm text-[13px] text-muted">{hint}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, className }: { error: unknown; onRetry?: () => void; className?: string }) {
  const { t, locale } = useI18n();
  const forbidden = error instanceof ApiError && error.status === 403;
  const msg = error instanceof ApiError ? (locale === "ar" ? error.messageAr : error.message) : t.errors.generic;
  return (
    <div role="alert" className={cn("flex flex-col items-center gap-2 px-6 py-12 text-center", className)}>
      <div className="grid size-11 place-items-center rounded-full bg-danger-soft text-danger">
        {forbidden ? <ShieldAlert className="size-5" /> : <AlertCircle className="size-5" />}
      </div>
      <p className="text-[15px] font-medium">{forbidden ? t.errors.forbidden : t.common.errorTitle}</p>
      {!forbidden && <p className="max-w-md text-[13px] text-muted">{msg}</p>}
      {onRetry && !forbidden && <Button variant="secondary" size="sm" className="mt-2" onClick={onRetry}>{t.common.retry}</Button>}
    </div>
  );
}

export function Notice({ tone = "neutral", icon: Icon, children, className }: {
  tone?: "neutral" | "warning" | "danger" | "info"; icon?: React.ElementType; children: React.ReactNode; className?: string;
}) {
  const s = { neutral: "bg-surface-2 text-ink-2 border-line", warning: "bg-warning-soft text-[#7a4f0a] border-[#f1e0bd]",
    danger: "bg-danger-soft text-[#8f2a30] border-[#f5d3d5]", info: "bg-primary-soft text-[#1d47b0] border-[#d3e0fa]" }[tone];
  return (
    <div className={cn("flex items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-[13px] leading-relaxed", s, className)}>
      {Icon && <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />}
      <div>{children}</div>
    </div>
  );
}
