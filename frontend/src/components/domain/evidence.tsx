"use client";

import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, CircleDashed, FileText } from "lucide-react";
import { useState } from "react";
import { Drawer } from "@/components/ui/dialog";
import { ErrorState, SkeletonRows } from "@/components/ui/feedback";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Citation } from "@/lib/types";
import { cn } from "@/lib/utils";

type ChunkDetail = {
  id: string; text: string; section: string; page_number: number | null;
  document: { document_code: string; title_ar: string; title_en: string; is_synthetic: boolean; classification: string };
  version: { version_label: string; status: string; publication_date: string | null; effective_date: string | null };
  context: { id: string; text: string; section: string; page_number: number | null; is_target: boolean }[];
};

/** Highlights the quoted sentence inside the passage (whitespace-insensitive). */
function Highlighted({ text, quote }: { text: string; quote?: string }) {
  if (!quote) return <>{text}</>;
  const q = quote.trim().replace(/\s+/g, " ");
  const flat = text.replace(/\s+/g, " ");
  const i = flat.indexOf(q);
  if (i < 0) return <>{text}</>;
  return <>{flat.slice(0, i)}<mark className="rounded-[3px] bg-[#fff1c7] px-0.5 text-ink">{flat.slice(i, i + q.length)}</mark>{flat.slice(i + q.length)}</>;
}

export function SourceDrawer({ chunkId, quote, open, onOpenChange }: { chunkId: string | null; quote?: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t, pick, fmtDate } = useI18n();
  const q = useQuery({ queryKey: ["chunk", chunkId], queryFn: () => api<ChunkDetail>(`/regulatory/chunks/${chunkId}`), enabled: open && !!chunkId });
  const d = q.data;
  return (
    <Drawer open={open} onOpenChange={onOpenChange} title={d ? pick(d.document.title_ar, d.document.title_en) || d.document.document_code : t.intel.passage}
      subtitle={d && (
        <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="ltr">{d.document.document_code} v{d.version.version_label}</span>
          <span>{d.section}</span>
          <span>{d.page_number ? `${t.intel.page} ${d.page_number}` : t.intel.noPage}</span>
          {d.version.status !== "ACTIVE" && <span className="text-warning">{t.intel.superseded}</span>}
          {d.document.is_synthetic && <span className="text-warning">{t.kb.synthetic}</span>}
        </span>
      )}>
      {q.isLoading && <SkeletonRows rows={6} />}
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {d && (
        <div className="flex flex-col gap-1">
          <p className="mb-2 text-[12.5px] text-muted">{t.intel.context}</p>
          {d.context.map((c) => (
            <div key={c.id} className={cn("rounded-lg px-4 py-3 text-[14px] leading-[1.9]", c.is_target ? "border border-primary/30 bg-primary-soft/40" : "text-muted")}>
              {c.section && c.section !== d.section && <p className="mb-1 text-[12px] font-medium text-ink-2">{c.section}</p>}
              <p className="whitespace-pre-line">{c.is_target ? <Highlighted text={c.text} quote={quote} /> : c.text}</p>
            </div>
          ))}
          <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-line pt-4 text-[12.5px]">
            <div><dt className="text-muted">{t.kb.publication}</dt><dd>{d.version.publication_date ? fmtDate(d.version.publication_date) : t.kb.notSupplied}</dd></div>
            <div><dt className="text-muted">{t.kb.effective}</dt><dd>{d.version.effective_date ? fmtDate(d.version.effective_date) : t.kb.notSupplied}</dd></div>
            <div><dt className="text-muted">{t.kb.classification}</dt><dd>{(t.kb as Record<string, string>)[d.document.classification]}</dd></div>
            <div><dt className="text-muted">{t.common.status}</dt><dd>{d.version.status === "ACTIVE" ? t.kb.active : t.kb.superseded}</dd></div>
          </dl>
        </div>
      )}
    </Drawer>
  );
}

/** The "evidence thread": numbered markers that open the exact passage behind a finding. */
export function EvidenceThread({ citations, startIndex = 1 }: { citations: Citation[]; startIndex?: number }) {
  const { t, pick } = useI18n();
  const [open, setOpen] = useState<Citation | null>(null);
  if (!citations.length) return null;
  return (
    <>
      <ol className="mt-3 flex flex-col gap-2">
        {citations.map((c, i) => {
          const regulatory = !!c.chunk_id;
          return (
            <li key={c.id}>
              <button type="button" disabled={!regulatory} onClick={() => setOpen(c)}
                className={cn("group flex w-full items-start gap-3 rounded-lg border border-line bg-canvas/60 px-3 py-2.5 text-start transition-colors",
                  regulatory && "hover:border-primary/40 hover:bg-primary-soft/30")}>
                <span className="mt-0.5 grid size-[22px] shrink-0 place-items-center rounded-full bg-ink text-[11px] font-semibold text-white num">{startIndex + i}</span>
                <span className="min-w-0 flex-1">
                  {c.quote && <span className="block text-[13px] leading-relaxed text-ink-2 line-clamp-3">«{c.quote}»</span>}
                  <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[12px] text-muted">
                    {regulatory ? (
                      <>
                        <span className="ltr font-medium text-ink-2">{c.document_code} v{c.version_label}</span>
                        {c.section && <span>{c.section}</span>}
                        <span>{c.page_number ? `${t.intel.page} ${c.page_number}` : t.intel.noPage}</span>
                      </>
                    ) : (
                      <span className="inline-flex items-center gap-1"><FileText className="size-3.5" />{t.assess.appDocument}</span>
                    )}
                    <span className={cn("inline-flex items-center gap-1", c.verified ? "text-success" : "text-warning")}>
                      {c.verified ? <BadgeCheck className="size-3.5" /> : <CircleDashed className="size-3.5" />}
                      {c.verified ? t.intel.verified : t.intel.unverified}
                    </span>
                  </span>
                </span>
                {regulatory && <span className="hidden self-center text-[12px] font-medium text-primary group-hover:inline">{pick("عرض", "View")}</span>}
              </button>
            </li>
          );
        })}
      </ol>
      <SourceDrawer chunkId={open?.chunk_id ?? null} quote={open?.quote} open={!!open} onOpenChange={(o) => !o && setOpen(null)} />
    </>
  );
}
