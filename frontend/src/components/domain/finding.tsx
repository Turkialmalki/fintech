"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import type { Finding } from "@/lib/types";
import { cn } from "@/lib/utils";
import { OriginTag, Severity } from "./badges";
import { EvidenceThread } from "./evidence";

/** A finding separates evidence (what the source says) from interpretation (model/analyst view). */
export function FindingItem({ f, defaultOpen = false, actions, citationStart = 1 }: {
  f: Finding; defaultOpen?: boolean; actions?: React.ReactNode; citationStart?: number;
}) {
  const { t, pick, label } = useI18n();
  const [open, setOpen] = useState(defaultOpen);
  const accent = { CRITICAL: "bg-danger", HIGH: "bg-danger-base", MEDIUM: "bg-warning-base", LOW: "bg-success", INFO: "bg-accent" }[f.severity] ?? "bg-line-strong";
  return (
    <article className="relative overflow-hidden rounded-lg border border-line bg-surface">
      <span className={cn("absolute inset-y-0 start-0 w-[3px]", accent)} aria-hidden />
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
        className="flex w-full items-start gap-4 px-5 py-3.5 text-start hover:bg-canvas/60">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <Severity value={f.severity} />
            <span className="text-[12px] text-muted">{label("findingCat", f.category)}</span>
            {f.requirement_code && <span className="ltr text-[12px] text-faint">{f.requirement_code}</span>}
          </div>
          <h3 className="mt-1 text-[14px] font-medium leading-snug text-ink">{pick(f.title_ar, f.title_en)}</h3>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {f.citations.length > 0 && <span className="text-[12px] text-muted num">{f.citations.length} {t.assess.sources}</span>}
          <OriginTag origin={f.origin} />
          <ChevronDown className={cn("size-4 text-muted transition-transform", open && "rotate-180")} aria-hidden />
        </div>
      </button>
      {open && (
        <div className="border-t border-line px-5 pb-4 pt-3.5">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="text-[12px] font-medium text-muted">{t.assess.evidence}</p>
              <p className="mt-1 whitespace-pre-line text-[13.5px] leading-relaxed text-ink">{pick(f.evidence_ar, f.evidence_en) || "—"}</p>
            </div>
            <div>
              <p className="text-[12px] font-medium text-muted">{t.assess.interpretation}</p>
              <p className="mt-1 text-[13.5px] leading-relaxed text-ink-2">{pick(f.interpretation_ar, f.interpretation_en) || "—"}</p>
              {f.uncertainty && <p className="mt-2 text-[12px] text-muted"><span className="font-medium">{t.assess.uncertainty}: </span><span dir="auto">{label("uncertainty", f.uncertainty) === "—" ? f.uncertainty : label("uncertainty", f.uncertainty)}</span></p>}
            </div>
          </div>
          <EvidenceThread citations={f.citations} startIndex={citationStart} />
          {actions && <div className="mt-3 flex flex-wrap gap-2 border-t border-line pt-3">{actions}</div>}
        </div>
      )}
    </article>
  );
}
