"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ArrowRight, Languages } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { LoginShowcase } from "@/components/marketing/showcase";
import { LogoMark } from "@/components/shell/logo";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/field";
import { Notice } from "@/components/ui/feedback";
import { api, ApiError, tokens } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

function LoginForm() {
  const { t, locale, setLocale, pick } = useI18n();
  const Arrow = locale === "ar" ? ArrowLeft : ArrowRight;
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const schema = z.object({
    email: z.string().email(pick("أدخل بريداً إلكترونياً صحيحاً", "Enter a valid email")),
    password: z.string().min(1, pick("أدخل كلمة المرور", "Enter your password")),
  });
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });

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
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <section className="relative flex flex-col overflow-hidden px-6 py-7 sm:px-12">
        <div className="pointer-events-none absolute -top-40 start-1/2 size-[520px] -translate-x-1/2 rounded-full bg-[radial-gradient(closest-side,rgba(36,87,214,0.10),transparent)]" aria-hidden />
        <div className="relative flex items-center justify-between">
          <div className="flex items-center gap-2.5"><LogoMark size={36} /><span className="leading-tight"><span className="block text-[15px] font-semibold">{t.brand.name}</span><span className="ltr block text-[11px] text-muted">Regulatory Intelligence Platform</span></span></div>
          <Button variant="ghost" size="sm" onClick={() => setLocale(locale === "ar" ? "en" : "ar")}><Languages />{t.common.language}</Button>
        </div>

        <div className="relative mx-auto flex w-full max-w-[400px] flex-1 flex-col justify-center py-10">
          <div className="rounded-2xl border border-line bg-surface p-7 shadow-[0_20px_50px_-28px_rgba(20,34,56,0.35)] sm:p-8">
            <h1 className="text-[26px] font-semibold tracking-[-0.01em]">{pick("مرحباً بعودتك", "Welcome back")}</h1>
            <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted">{pick("سجّل الدخول لمتابعة الطلبات والتقييمات والمراجعات.", "Sign in to continue with applications, assessments and reviews.")}</p>
            <form onSubmit={onSubmit} className="mt-7 flex flex-col gap-4" noValidate>
              {error && <Notice tone="danger">{error}</Notice>}
              <Field label={t.login.email} htmlFor="email" error={errors.email?.message}>
                <Input id="email" type="email" dir="ltr" autoComplete="username" placeholder="name@company.sa" className="h-11 text-start" aria-invalid={!!errors.email} {...register("email")} />
              </Field>
              <Field label={t.login.password} htmlFor="password" error={errors.password?.message}>
                <Input id="password" type="password" dir="ltr" autoComplete="current-password" className="h-11" aria-invalid={!!errors.password} {...register("password")} />
              </Field>
              <Button type="submit" size="lg" loading={isSubmitting} className="mt-1 h-12 rounded-xl text-[15.5px]">{isSubmitting ? t.login.submitting : t.login.submit}</Button>
            </form>
            <p className="mt-4 text-center text-[12.5px] text-muted">{t.login.forgot}</p>
          </div>

          <Link href="/readiness" className="group mt-5 flex items-center gap-4 rounded-2xl border border-primary/15 bg-gradient-to-l from-primary-soft/70 to-surface p-4 transition-colors hover:border-primary/40">
            <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary text-white shadow-[0_8px_20px_-8px_rgba(36,87,214,0.7)]"><Arrow className="size-[18px] transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" /></span>
            <span>
              <span className="block text-[14.5px] font-semibold">{pick("افحص جاهزية شركتك مجاناً", "Check your company's readiness")}</span>
              <span className="mt-0.5 block text-[12.5px] text-muted">{pick("دون تسجيل — ارفع وثائقك واحصل على الفجوات والخطوات التالية.", "No sign-up — upload documents, get gaps and next steps.")}</span>
            </span>
          </Link>
        </div>

        <p className="relative text-center text-[11.5px] text-faint">{pick("بياناتك محمية · اتصال مشفّر · سجل تدقيق لكل عملية", "Protected data · Encrypted connection · Every action audited")}</p>
      </section>

      <LoginShowcase />
    </div>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
