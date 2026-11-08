"use client";

import { BadgeCheck, BookOpenText, ExternalLink, FileCheck2, ScanSearch, ShieldCheck, Sparkles } from "lucide-react";
import { ScoreRing } from "@/components/marketing/preview";
import { useI18n } from "@/lib/i18n";

const glass = "rounded-2xl border border-white/15 bg-[#0d1b3d]/55 shadow-[0_24px_60px_-20px_rgba(0,0,0,0.65)] backdrop-blur-xl";

/** Login-side showcase: original night-skyline artwork with layered cards that show what the platform does. */
export function LoginShowcase() {
  const { pick } = useI18n();
  const bars = [
    { l: pick("الشراء الآن والدفع لاحقاً", "BNPL"), v: 86, c: "#7fd4b2" },
    { l: pick("المدفوعات", "Payments"), v: 64, c: "#8fb4ff" },
    { l: pick("المصرفية المفتوحة", "Open banking"), v: 91, c: "#7fd4b2" },
    { l: pick("التمويل المصغر", "Microfinance"), v: 47, c: "#f2c879" },
  ];
  return (
    <aside className="relative hidden overflow-hidden bg-[#071029] text-white lg:block">
      <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: "url(/login-bg.webp)" }} aria-hidden />
      <div className="absolute inset-0 bg-gradient-to-b from-[#071029]/85 via-[#071029]/20 to-[#071029]/70" aria-hidden />

      <div className="relative flex h-full flex-col px-12 pb-10 pt-14 xl:px-16">
        <div className="max-w-[580px] animate-rise">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.06] px-3 py-1 text-[12px] text-[#bcd2ff] backdrop-blur">
            <Sparkles className="size-3.5" />{pick("ذكاء تنظيمي مدعوم بـ RAG", "RAG-powered regulatory intelligence")}
          </span>
          <h2 className="mt-4 text-[30px] font-semibold leading-[1.3] tracking-[-0.01em] xl:text-[34px]">
            {pick("من الوثائق إلى قرار الجاهزية — في دقائق", "From documents to a readiness decision — in minutes")}
          </h2>
          <p className="mt-3 text-[15px] leading-relaxed text-white/70">
            {pick("نحلل وثائق شركات التقنية المالية ونطابقها مع متطلبات البنك المركزي السعودي وسدايا ومكافحة غسل الأموال، وكل نتيجة مرتبطة بنصها الرسمي.",
              "We analyse fintech documents against SAMA, SDAIA and AML requirements — every finding linked to its official text.")}
          </p>
        </div>

        {/* layered cards */}
        <div className="flex flex-1 items-center"><div className="relative h-[380px] w-full max-w-[600px]">
          {/* readiness score */}
          <div className={`${glass} absolute start-0 top-0 w-[285px] p-5 animate-float`}>
            <p className="text-[12px] text-[#9fb4e8]">{pick("نسبة الجاهزية", "Readiness score")}</p>
            <div className="mt-3 flex items-center gap-4">
              <ScoreRing value={82} size={92} stroke={9} tone="#7fd4b2">
                <p className="ltr text-[22px] font-semibold">82<span className="text-[12px] text-white/60">%</span></p>
              </ScoreRing>
              <div className="text-[12.5px] leading-6 text-white/80">
                <p><span className="ltr font-semibold text-[#7fd4b2]">14</span> {pick("متطلباً مستوفى", "requirements met")}</p>
                <p><span className="ltr font-semibold text-[#f3a1a6]">2</span> {pick("فجوة", "gaps")}</p>
                <p><span className="ltr font-semibold text-[#f2c879]">1</span> {pick("مؤشر مخاطر", "risk flag")}</p>
              </div>
            </div>
          </div>

          {/* readiness by activity */}
          <div className={`${glass} absolute end-0 top-8 w-[270px] p-4 animate-float [animation-delay:-2s]`}>
            <p className="flex items-center gap-1.5 text-[12px] text-[#9fb4e8]"><ScanSearch className="size-3.5" />{pick("متوسط الجاهزية حسب النشاط", "Avg readiness by activity")}</p>
            <ul className="mt-3 flex flex-col gap-2.5">
              {bars.map((b) => (
                <li key={b.l} className="text-[12px]">
                  <div className="flex justify-between text-white/75"><span>{b.l}</span><span className="ltr">{b.v}%</span></div>
                  <div className="mt-1 h-1.5 rounded-full bg-white/10"><div className="h-full rounded-full" style={{ width: `${b.v}%`, background: b.c }} /></div>
                </li>
              ))}
            </ul>
          </div>

          {/* document verified */}
          <div className={`${glass} absolute start-0 top-[200px] flex w-[285px] items-center gap-3 px-4 py-3 animate-float [animation-delay:-4s]`}>
            <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-[#7fd4b2]/15 text-[#7fd4b2]"><FileCheck2 className="size-[18px]" /></span>
            <div className="min-w-0">
              <p className="text-[13px] font-medium">{pick("سياسة مكافحة غسل الأموال", "AML/CTF policy")}</p>
              <p className="text-[11.5px] text-white/60">{pick("وثيقة مقبولة · 6 من 7 عناصر أساسية", "Accepted · 6 of 7 core elements")}</p>
            </div>
            <BadgeCheck className="ms-auto size-5 text-[#7fd4b2]" />
          </div>

          {/* cited regulation */}
          <div className={`${glass} absolute end-0 top-[262px] w-[270px] p-4 animate-float [animation-delay:-1s]`}>
            <p className="flex items-center gap-1.5 text-[12px] text-[#9fb4e8]"><BookOpenText className="size-3.5" />{pick("الاستشهاد من المصدر الرسمي", "Cited from the official source")}</p>
            <p className="mt-2 border-s-2 border-[#5B86F0] ps-3 text-[12.5px] leading-relaxed text-white/85">
              {pick("«الحد الأدنى لرأس مال شركة الشراء الآن والدفع لاحقاً خمسة ملايين ريال»", "“Minimum capital for a BNPL company is SAR 5 million”")}
            </p>
            <p className="mt-2 flex items-center gap-2 text-[11.5px] text-white/55">
              <span>{pick("ساما · المادة 5", "SAMA · Art. 5")}</span>
              <span className="ltr inline-flex items-center gap-1 text-[#9fb4e8]"><ExternalLink className="size-3" />rulebook.sama.gov.sa</span>
            </p>
          </div>

          {/* human review chip */}
          <div className={`${glass} absolute start-0 top-[300px] flex items-center gap-2 rounded-full px-4 py-2 text-[12.5px] animate-float [animation-delay:-3s]`}>
            <ShieldCheck className="size-4 text-[#8fb4ff]" />{pick("قرار نهائي بمراجعة بشرية وسجل تدقيق كامل", "Human sign-off with a full audit trail")}
          </div>
        </div></div>

        <div className="relative flex flex-wrap gap-x-6 gap-y-2 text-[12px] text-white/60">
          {[pick("البنك المركزي السعودي", "SAMA"), pick("سدايا · حماية البيانات", "SDAIA · PDPL"), pick("مكافحة غسل الأموال", "AML/CTF"), pick("الأمن السيبراني", "Cyber security")].map((s) => (
            <span key={s} className="inline-flex items-center gap-1.5"><span className="size-1.5 rounded-full bg-[#7fd4b2]" />{s}</span>
          ))}
        </div>
      </div>
    </aside>
  );
}
