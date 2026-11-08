"use client";

import { BookOpenText, FileCheck2, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { useI18n } from "@/lib/i18n";

const SLIDES = [
  { src: "/login/kafd-1.webp", pos: "50% 60%" },
  { src: "/login/kafd-2.webp", pos: "50% 40%" },
  { src: "/login/kafd-3.webp", pos: "50% 45%" },
];

/** Login-side panel: photography of Riyadh's financial district with a calm, static message. */
export function LoginShowcase() {
  const { pick } = useI18n();
  const [i, setI] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = setInterval(() => setI((n) => (n + 1) % SLIDES.length), 8000);
    return () => clearInterval(id);
  }, []);

  const points = [
    { icon: FileCheck2, t: pick("فحص الوثائق والتحقق من اكتمالها", "Document checks and completeness") },
    { icon: BookOpenText, t: pick("كل نتيجة مرتبطة بنصها الرسمي", "Every finding linked to its official text") },
    { icon: ShieldCheck, t: pick("قرار نهائي بمراجعة بشرية", "Final decisions by a human reviewer") },
  ];

  return (
    <aside className="relative hidden overflow-hidden bg-[#0b1220] text-white lg:block">
      {SLIDES.map((s, n) => (
        <div key={s.src} aria-hidden
          className="absolute inset-0 bg-cover transition-opacity duration-[1600ms] ease-out"
          style={{ backgroundImage: `url(${s.src})`, backgroundPosition: s.pos, opacity: n === i ? 1 : 0 }} />
      ))}
      {/* legibility: soft top fade, strong bottom fade where the text sits */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#0b1220]/45 via-transparent to-transparent" aria-hidden />
      <div className="absolute inset-x-0 bottom-0 h-[62%] bg-gradient-to-t from-[#0b1220] via-[#0b1220]/80 to-transparent" aria-hidden />

      <div className="relative flex h-full flex-col justify-end px-12 pb-12 xl:px-16">
        <p className="text-[12.5px] font-medium tracking-wide text-white/70">{pick("منظومة الرصد التنظيمي الذكي", "Regulatory Intelligence Platform")}</p>
        <h2 className="mt-3 max-w-[560px] text-[32px] font-semibold leading-[1.3] tracking-[-0.01em] xl:text-[36px]">
          {pick("جاهزية القطاع التقني المالي", "Fintech sector readiness")}
        </h2>
        <p className="mt-3 max-w-[520px] text-[15px] leading-relaxed text-white/75">
          {pick("نطابق نموذج العمل والوثائق مع متطلبات البنك المركزي السعودي وسدايا ومكافحة غسل الأموال باستخدام تقنية RAG، ليحصل المحلل على نتائج مسندة إلى مصادرها الرسمية.",
            "We match business models and documents against SAMA, SDAIA and AML requirements using RAG, so analysts get findings grounded in their official sources.")}
        </p>

        <ul className="mt-8 grid max-w-[600px] gap-3 sm:grid-cols-3">
          {points.map((p) => (
            <li key={p.t} className="flex items-start gap-2.5 border-t border-white/20 pt-3 text-[13px] leading-snug text-white/85">
              <p.icon className="mt-0.5 size-4 shrink-0 text-white/70" />{p.t}
            </li>
          ))}
        </ul>

        <div className="mt-8 flex items-center gap-1.5" aria-hidden>
          {SLIDES.map((s, n) => (
            <span key={s.src} className={`h-1 rounded-full transition-all duration-500 ${n === i ? "w-6 bg-white" : "w-2 bg-white/40"}`} />
          ))}
        </div>
      </div>
    </aside>
  );
}
