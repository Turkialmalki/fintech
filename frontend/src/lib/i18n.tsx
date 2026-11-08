"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ar, en, labels, type Dict, type LabelGroup } from "./dictionaries";

export type Locale = "ar" | "en";
const COOKIE = "rip_locale";

type Ctx = {
  locale: Locale;
  dir: "rtl" | "ltr";
  t: Dict;
  setLocale: (l: Locale) => void;
  label: (group: LabelGroup, key: string | null | undefined) => string;
  pick: <T>(arValue: T, enValue: T) => T;
  fmtNum: (n: number | null | undefined, opts?: Intl.NumberFormatOptions) => string;
  fmtDate: (d: string | Date | null | undefined, withTime?: boolean) => string;
  fmtRelative: (d: string | Date) => string;
};

const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ initial, children }: { initial: Locale; children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(initial);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    document.cookie = `${COOKIE}=${l}; path=/; max-age=31536000; samesite=lax`;
    try { localStorage.setItem(COOKIE, l); } catch { /* storage unavailable */ }
  }, []);

  useEffect(() => {
    const html = document.documentElement;
    html.lang = locale;
    html.dir = locale === "ar" ? "rtl" : "ltr";
  }, [locale]);

  const value = useMemo<Ctx>(() => {
    // Saudi business convention in data-dense UIs: Arabic text with Latin digits for scanability.
    const numLocale = locale === "ar" ? "ar-SA-u-nu-latn" : "en-US";
    return {
      locale,
      dir: locale === "ar" ? "rtl" : "ltr",
      t: locale === "ar" ? ar : en,
      setLocale,
      label: (group, key) => {
        if (!key) return "—";
        const entry = (labels[group] as Record<string, readonly [string, string]>)[key];
        return entry ? entry[locale === "ar" ? 0 : 1] : key;
      },
      pick: (a, e) => (locale === "ar" ? a : e),
      fmtNum: (n, opts) => (n === null || n === undefined || Number.isNaN(n) ? "—" : new Intl.NumberFormat(numLocale, opts).format(n)),
      fmtDate: (d, withTime) => {
        if (!d) return "—";
        const date = typeof d === "string" ? new Date(d) : d;
        return new Intl.DateTimeFormat(numLocale, withTime
          ? { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }
          : { year: "numeric", month: "short", day: "numeric" }).format(date);
      },
      fmtRelative: (d) => {
        const date = typeof d === "string" ? new Date(d) : d;
        const diff = (date.getTime() - Date.now()) / 1000;
        const rtf = new Intl.RelativeTimeFormat(numLocale, { numeric: "auto" });
        const abs = Math.abs(diff);
        if (abs < 60) return rtf.format(Math.round(diff), "second");
        if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
        if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
        return rtf.format(Math.round(diff / 86400), "day");
      },
    };
  }, [locale, setLocale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside I18nProvider");
  return ctx;
}

export const LOCALE_COOKIE = COOKIE;
