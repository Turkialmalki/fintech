"use client";

import Link from "next/link";
import { useI18n } from "@/lib/i18n";

/** Original mark: a lens over three stacked rule lines — reading regulation closely. */
export function LogoMark({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="8" fill="#142238" />
      <path d="M8 10.5h11M8 15h8M8 19.5h6" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" opacity=".9" />
      <circle cx="20.5" cy="18.5" r="4.6" fill="none" stroke="#5B86F0" strokeWidth="2" />
      <path d="m24 22 2.6 2.6" stroke="#5B86F0" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

export function Logo({ compact }: { compact?: boolean }) {
  const { t } = useI18n();
  return (
    <Link href="/" className="flex items-center gap-2.5" aria-label={t.brand.name}>
      <LogoMark />
      {!compact && (
        <span className="leading-tight">
          <span className="block text-[14px] font-semibold text-ink">{t.brand.short}</span>
          <span className="block text-[11px] text-muted ltr">RIP — Fintech supervision</span>
        </span>
      )}
    </Link>
  );
}
