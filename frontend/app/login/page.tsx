"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, ArrowRight, Languages } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ProductPreview } from "@/components/marketing/preview";
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
          <p className="mt-4 text-center text-[12.5px] text-muted">{t.login.forgot}</p>
          <Link href="/readiness" className="group mt-10 flex items-center gap-4 rounded-xl border border-line bg-surface p-4 transition-colors hover:border-primary/40 hover:bg-primary-soft/30">
            <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-primary-soft text-primary"><Arrow className="size-[18px] transition-transform group-hover:-translate-x-0.5 rtl:group-hover:translate-x-0.5" /></span>
            <span>
              <span className="block text-[14px] font-semibold">{pick("افحص جاهزية شركتك مجاناً", "Check your company's readiness")}</span>
              <span className="mt-0.5 block text-[12.5px] text-muted">{pick("دون تسجيل — ارفع وثائقك واحصل على الفجوات والخطوات التالية خلال دقائق.", "No sign-up — upload your documents and get gaps and next steps in minutes.")}</span>
            </span>
          </Link>
        </div>
      </section>

      {/* Brand panel: what a readiness result looks like */}
      <aside className="relative hidden overflow-hidden bg-[#0d1830] text-white lg:flex lg:flex-col lg:justify-center lg:px-14 xl:px-20">
        <div className="absolute inset-0 opacity-[0.06]" aria-hidden
          style={{ backgroundImage: "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)", backgroundSize: "40px 40px" }} />
        <div className="relative animate-rise">
          <h2 className="max-w-[520px] text-[30px] font-semibold leading-[1.3] tracking-[-0.01em]">{pick("اعرف جاهزيتك التنظيمية قبل أن تتقدم بطلب الترخيص", "Know your regulatory readiness before you apply")}</h2>
          <p className="mt-3 max-w-[500px] text-[14.5px] leading-relaxed text-white/65">{pick("مطابقة نموذج عملك ووثائقك مع متطلبات البنك المركزي السعودي وسدايا ومكافحة غسل الأموال، مع رابط للمصدر الرسمي لكل متطلب.", "Match your business model and documents against SAMA, SDAIA and AML requirements — every requirement linked to its official source.")}</p>
          <div className="mt-9"><ProductPreview /></div>
        </div>
      </aside>
    </div>
  );
}

export default function LoginPage() {
  return <Suspense><LoginForm /></Suspense>;
}
