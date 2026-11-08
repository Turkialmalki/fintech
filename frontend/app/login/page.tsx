"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Languages } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { LogoMark } from "@/components/shell/logo";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Notice } from "@/components/ui/feedback";
import { api, ApiError, tokens } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const DEMO = [
  { email: "analyst@rip.demo", role: "analyst" }, { email: "supervisor@rip.demo", role: "supervisor" },
  { email: "admin@rip.demo", role: "admin" }, { email: "auditor@rip.demo", role: "auditor" },
];

function LoginForm() {
  const { t, locale, setLocale, label, pick } = useI18n();
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const schema = z.object({
    email: z.string().email(pick("أدخل بريداً إلكترونياً صحيحاً", "Enter a valid email")),
    password: z.string().min(1, pick("أدخل كلمة المرور", "Enter your password")),
  });
  const { register, handleSubmit, setValue, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (v) => {
    setError(null);
    try {
      const r = await api<{ access_token: string; refresh_token: string }>("/auth/login", { body: v });
      tokens.set(r.access_token, r.refresh_token);
      const next = params.get("next");
      router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/");
    } catch (e) {
      setError(e instanceof ApiError ? (locale === "ar" ? e.messageAr : e.message) : t.errors.network);
    }
  });

  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <section className="flex flex-col px-6 py-8 sm:px-12">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5"><LogoMark size={34} /><span className="text-[15px] font-semibold">{t.brand.name}</span></div>
          <Button variant="ghost" size="sm" onClick={() => setLocale(locale === "ar" ? "en" : "ar")}><Languages />{t.common.language}</Button>
        </div>
        <div className="mx-auto flex w-full max-w-[380px] flex-1 flex-col justify-center py-12">
          <h1 className="text-[28px] font-semibold tracking-[-0.01em]">{t.login.title}</h1>
          <p className="mt-2 text-[14px] text-muted">{t.login.subtitle}</p>
          <form onSubmit={onSubmit} className="mt-8 flex flex-col gap-4" noValidate>
            {error && <Notice tone="danger">{error}</Notice>}
            <Field label={t.login.email} htmlFor="email" error={errors.email?.message}>
              <Input id="email" type="email" dir="ltr" autoComplete="username" className="h-11 text-start" aria-invalid={!!errors.email} {...register("email")} />
            </Field>
            <Field label={t.login.password} htmlFor="password" error={errors.password?.message}>
              <Input id="password" type="password" dir="ltr" autoComplete="current-password" className="h-11" aria-invalid={!!errors.password} {...register("password")} />
            </Field>
            <Button type="submit" size="lg" loading={isSubmitting} className="mt-2">{isSubmitting ? t.login.submitting : t.login.submit}</Button>
          </form>
          <div className="mt-10 border-t border-line pt-5">
            <p className="text-[13px] font-medium text-ink-2">{t.login.demoAccounts}</p>
            <p className="mt-0.5 text-[12.5px] text-muted">{t.login.demoPassword}: <span className="ltr font-medium text-ink">Demo@2026!</span></p>
            <ul className="mt-3 grid grid-cols-2 gap-2">
              {DEMO.map((d) => (
                <li key={d.email}>
                  <button type="button" onClick={() => { setValue("email", d.email); setValue("password", "Demo@2026!"); }}
                    className="w-full rounded-md border border-line px-3 py-2 text-start hover:border-primary/40 hover:bg-primary-soft/40">
                    <span className="block text-[13px] font-medium">{label("role", d.role)}</span>
                    <span className="ltr block truncate text-[11.5px] text-muted">{d.email}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
        <p className="text-[12px] leading-relaxed text-muted">{t.demo.banner}</p>
      </section>

      {/* Brand panel: the product's core idea — every finding traced to its exact source */}
      <aside className="relative hidden overflow-hidden bg-ink text-white lg:flex lg:flex-col lg:justify-center lg:px-16">
        <div className="absolute inset-0 opacity-[0.07]" aria-hidden
          style={{ backgroundImage: "linear-gradient(#fff 1px, transparent 1px)", backgroundSize: "100% 28px" }} />
        <div className="relative max-w-[520px] animate-rise">
          <p className="text-[13px] text-[#9fb4e8]">{pick("مثال توضيحي من بيانات اصطناعية", "Illustrative example from synthetic data")}</p>
          <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.04] p-5">
            <div className="flex items-center gap-2 text-[12px] text-[#f0b9bc]">
              <span className="inline-flex items-end gap-[2px]" aria-hidden>{[0, 1, 2, 3].map((i) => <span key={i} className={`w-[3px] rounded-full ${i < 3 ? "bg-[#ef7c82]" : "bg-white/20"}`} style={{ height: 6 + i * 3 }} />)}</span>
              {pick("فجوة محتملة · أهمية عالية", "Potential gap · High")}
            </div>
            <p className="mt-2 text-[17px] font-medium leading-snug">{pick("رأس المال المدفوع أقل من الحد المهيأ لخدمات الشراء الآن والدفع لاحقاً", "Paid-up capital below the configured minimum for BNPL services")}</p>
            <div className="mt-4 border-s-2 border-[#5B86F0] ps-4">
              <p className="text-[13.5px] leading-relaxed text-white/80">{pick("«يجب ألا يقل رأس المال المدفوع لمقدمي خدمات الشراء الآن والدفع لاحقاً والتمويل الرقمي عن عشرة ملايين ريال سعودي»", "“Paid-up capital for BNPL and digital lending providers must not be less than SAR 10 million”")}</p>
              <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-white/55">
                <span className="ltr">RIP-SYN-001 · v2026.1</span><span>{pick("المادة 2", "Article 2")}</span>
                <span className="inline-flex items-center gap-1 text-[#7fd4b2]">✓ {pick("اقتباس متحقق منه", "Quote verified")}</span>
              </p>
            </div>
          </div>
          <ul className="mt-10 flex flex-col gap-3.5">
            {t.login.pillars.map((p) => (
              <li key={p} className="flex items-center gap-3 text-[14.5px] text-white/85"><span className="h-px w-6 bg-[#5B86F0]" aria-hidden />{p}</li>
            ))}
          </ul>
        </div>
      </aside>
    </div>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
