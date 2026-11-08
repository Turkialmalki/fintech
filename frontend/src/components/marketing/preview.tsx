"use client";

import { Check, ExternalLink, FileUp, ListChecks, ScanSearch, TriangleAlert, X } from "lucide-react";
import { useI18n } from "@/lib/i18n";

/** Score ring used by the product preview and the readiness results. */
export function ScoreRing({ value, size = 128, stroke = 10, tone = "#5B86F0", track = "rgba(255,255,255,0.12)", children }: {
  value: number; size?: number; stroke?: number; tone?: string; track?: string; children?: React.ReactNode;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative inline-grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={tone} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - Math.max(0, Math.min(100, value)) / 100)}
          style={{ transition: "stroke-dashoffset 900ms cubic-bezier(.2,.7,.2,1)" }} />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">{children}</div>
    </div>
  );
}

/** A worked example of a readiness result, drawn with real rules and their official sources. */
export function ProductPreview() {
  const { pick } = useI18n();
  const rows = [
    { icon: Check, tone: "text-[#7fd4b2] bg-[#7fd4b2]/12", title: pick("رأس المال 5.5 مليون ريال ≥ الحد الأدنى 5 ملايين", "Capital SAR 5.5M ≥ SAR 5M minimum"), src: pick("قواعد الشراء الآن والدفع لاحقاً · المادة 5", "BNPL Rules · Art. 5") },
    { icon: X, tone: "text-[#f3a1a6] bg-[#ef7c82]/14", title: pick("سياسة حماية العملاء والشكاوى غير مرفقة", "Consumer protection & complaints policy missing"), src: pick("قواعد الشراء الآن والدفع لاحقاً · المادة 17", "BNPL Rules · Art. 17") },
    { icon: TriangleAlert, tone: "text-[#f2c879] bg-[#f2c879]/12", title: pick("الاستضافة في فرانكفورت — يلزم إثبات ضوابط النقل", "Hosted in Frankfurt — transfer safeguards needed"), src: pick("نظام حماية البيانات الشخصية", "Personal Data Protection Law") },
  ];
  const steps = [
    { icon: FileUp, t: pick("ارفع وثائقك", "Upload documents") },
    { icon: ScanSearch, t: pick("مطابقة مع الأنظمة", "Match against rules") },
    { icon: ListChecks, t: pick("فجوات وخطوات تالية", "Gaps & next steps") },
  ];
  return (
    <div className="relative w-full max-w-[540px]">
      {/* glow */}
      <div className="pointer-events-none absolute -inset-10 rounded-[40px] bg-[radial-gradient(60%_50%_at_70%_20%,rgba(91,134,240,0.35),transparent_70%),radial-gradient(50%_40%_at_10%_90%,rgba(127,212,178,0.18),transparent_70%)] blur-2xl" aria-hidden />

      <div className="relative rounded-2xl border border-white/10 bg-white/[0.05] p-5 shadow-[0_30px_80px_-30px_rgba(0,0,0,0.6)] backdrop-blur-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[12px] text-[#9fb4e8]">{pick("مثال لنتيجة فحص", "Example result")}</p>
            <p className="mt-0.5 text-[15.5px] font-semibold">{pick("شركة شراء الآن والدفع لاحقاً", "A buy-now-pay-later company")}</p>
          </div>
          <span className="rounded-full border border-white/15 px-2.5 py-0.5 text-[11.5px] text-white/70">{pick("الشراء الآن والدفع لاحقاً", "BNPL")}</span>
        </div>

        <div className="mt-5 grid grid-cols-[auto_1fr] items-center gap-5">
          <ScoreRing value={72} size={116}>
            <div><p className="ltr text-[30px] font-semibold leading-none">72<span className="text-[15px] text-white/60">%</span></p>
              <p className="mt-1 text-[11px] text-white/60">{pick("جاهزية", "Readiness")}</p></div>
          </ScoreRing>
          <div className="grid grid-cols-3 gap-2 text-center">
            {[{ n: 11, l: pick("مستوفى", "Met"), c: "text-[#7fd4b2]" }, { n: 3, l: pick("فجوات", "Gaps"), c: "text-[#f3a1a6]" }, { n: 1, l: pick("مخاطر", "Risks"), c: "text-[#f2c879]" }].map((k) => (
              <div key={k.l} className="rounded-lg border border-white/10 bg-white/[0.03] px-2 py-2.5">
                <p className={`ltr text-[20px] font-semibold leading-none ${k.c}`}>{k.n}</p>
                <p className="mt-1 text-[11.5px] text-white/60">{k.l}</p>
              </div>
            ))}
          </div>
        </div>

        <ul className="mt-5 flex flex-col gap-2">
          {rows.map((r) => (
            <li key={r.title} className="flex items-start gap-3 rounded-lg border border-white/[0.07] bg-white/[0.025] px-3 py-2.5">
              <span className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full ${r.tone}`}><r.icon className="size-3.5" strokeWidth={2.5} /></span>
              <div className="min-w-0">
                <p className="text-[13.5px] leading-snug text-white/90">{r.title}</p>
                <p className="mt-0.5 text-[11.5px] text-white/45">{r.src}</p>
              </div>
            </li>
          ))}
        </ul>

        <div className="mt-4 border-s-2 border-[#5B86F0] ps-4">
          <p className="text-[13px] leading-relaxed text-white/75">
            {pick("«لا يتجاوز إجمالي التمويل القائم للعميل الفرد خمسة آلاف ريال، ولا يزيد عدد الأقساط على 12 قسطاً»",
              "“Total outstanding financing per consumer must not exceed SAR 5,000, in no more than 12 instalments”")}
          </p>
          <p className="mt-1.5 flex flex-wrap items-center gap-x-3 text-[11.5px] text-white/50">
            <span>{pick("البنك المركزي السعودي · المادة 22", "SAMA · Art. 22")}</span>
            <span className="ltr inline-flex items-center gap-1 text-[#9fb4e8]"><ExternalLink className="size-3" />rulebook.sama.gov.sa</span>
          </p>
        </div>
      </div>

      <ol className="relative mt-6 grid grid-cols-3 gap-2">
        {steps.map((s, i) => (
          <li key={s.t} className="flex items-center gap-2 text-[12.5px] text-white/75">
            <span className="grid size-7 shrink-0 place-items-center rounded-full border border-white/15 bg-white/[0.04]"><s.icon className="size-3.5" /></span>
            <span className="leading-tight">{s.t}</span>
            {i < steps.length - 1 && <span className="ms-auto hidden h-px w-4 bg-white/20 xl:block" aria-hidden />}
          </li>
        ))}
      </ol>
    </div>
  );
}
