"use client";

import { useQuery } from "@tanstack/react-query";
import { use, useState } from "react";
import { StatusBadge, SyntheticTag } from "@/components/domain/badges";
import { Badge } from "@/components/ui/badge";
import { ErrorState, SkeletonRows } from "@/components/ui/feedback";
import { DescList, PageHeader, Panel } from "@/components/ui/layout";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Version = { id: string; version_label: string; status: string; page_count: number; chunk_count: number; indexing_status: string; indexing_error: string;
  publication_date: string | null; effective_date: string | null; filename: string; created_at: string; extracted_metadata: Record<string, any>; sha256: string };
type Detail = { id: string; document_code: string; title_ar: string; title_en: string; source: string; language: string; classification: string;
  is_synthetic: boolean; tags: string[]; versions: Version[]; current_version: Version | null };
type Chunk = { id: string; chunk_index: number; page_number: number | null; section: string; text: string; language: string };

export default function RegDocDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t, pick, fmtDate, fmtNum } = useI18n();
  const q = useQuery({ queryKey: ["regdoc", id], queryFn: () => api<Detail>(`/regulatory/documents/${id}`) });
  const [versionId, setVersionId] = useState<string | null>(null);
  const vid = versionId ?? q.data?.current_version?.id;
  const chunks = useQuery({ queryKey: ["chunks", id, vid], queryFn: () => api<Chunk[]>(`/regulatory/documents/${id}/chunks`, { query: { version_id: vid } }), enabled: !!vid });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data;
  if (!d) return <SkeletonRows rows={8} />;
  const v = d.versions.find((x) => x.id === vid) ?? d.current_version;
  const sections = Array.from(new Map((chunks.data ?? []).filter((c) => c.section).map((c) => [c.section, c])).values());

  return (
    <div>
      <PageHeader title={pick(d.title_ar, d.title_en) || d.document_code} crumbs={[{ label: t.kb.title, href: "/knowledge" }, { label: d.document_code }]}
        meta={<><span className="ltr text-[13px] text-muted">{d.document_code}</span><Badge>{(t.kb as Record<string, string>)[d.classification]}</Badge>{d.is_synthetic && <SyntheticTag />}</>} />
      <div className="grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)]">
        <div className="flex flex-col gap-6 xl:sticky xl:top-24 xl:self-start">
          <Panel title={t.kb.versions} bodyClass="p-2">
            <ul className="flex flex-col gap-1">
              {d.versions.map((x) => (
                <li key={x.id}>
                  <button type="button" onClick={() => setVersionId(x.id)} aria-current={x.id === vid}
                    className={cn("flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-start text-[13px]", x.id === vid ? "bg-primary-soft/70" : "hover:bg-surface-2")}>
                    <span><span className="ltr font-medium">v{x.version_label}</span><span className="block text-[12px] text-muted">{fmtDate(x.created_at)}</span></span>
                    <Badge tone={x.status === "ACTIVE" ? "success" : "neutral"}>{x.status === "ACTIVE" ? t.kb.active : t.kb.superseded}</Badge>
                  </button>
                </li>
              ))}
            </ul>
          </Panel>
          {v && (
            <Panel title={t.kb.metadata}>
              <DescList cols={1} items={[
                { label: t.kb.source, value: d.source }, { label: t.kb.publication, value: v.publication_date ? fmtDate(v.publication_date) : t.kb.notSupplied },
                { label: t.kb.effective, value: v.effective_date ? fmtDate(v.effective_date) : t.kb.notSupplied },
                { label: t.kb.pages, value: v.extracted_metadata?.paginated === false ? t.intel.noPage : fmtNum(v.page_count) },
                { label: t.kb.chunks, value: fmtNum(v.chunk_count) }, { label: t.common.status, value: <StatusBadge status={v.indexing_status === "INDEXED" ? "SUCCEEDED" : "FAILED"} group="runStatus" /> },
                { label: t.kb.embedding, value: <span className="ltr">{v.extracted_metadata?.embedding_model}{v.extracted_metadata?.embedding_mock ? " (mock)" : ""}</span> },
                { label: t.kb.vectorBackend, value: <span className="ltr">{v.extracted_metadata?.vector_backend}</span> },
                { label: t.kb.sha, value: <span className="ltr break-all text-[11.5px] text-muted">{v.sha256}</span> },
              ]} />
            </Panel>
          )}
        </div>
        <Panel title={t.kb.sections} bodyClass="p-0">
          {!chunks.data ? <SkeletonRows className="p-5" /> : (
            <>
              <nav aria-label={t.kb.sections} className="flex flex-wrap gap-1.5 border-b border-line px-5 py-3">
                {sections.map((s) => <a key={s.id} href={`#c-${s.id}`} className="rounded-full border border-line px-2.5 py-0.5 text-[12px] text-ink-2 hover:border-primary/40">{s.section}</a>)}
              </nav>
              <div className="divide-y divide-line">
                {chunks.data.map((c) => (
                  <article key={c.id} id={`c-${c.id}`} className="scroll-mt-24 px-6 py-4">
                    <p className="mb-1.5 flex gap-3 text-[12px] text-muted">
                      <span className="num">#{c.chunk_index + 1}</span>{c.page_number && <span>{t.intel.page} {c.page_number}</span>}<span>{c.section}</span>
                    </p>
                    <p dir="auto" className="whitespace-pre-line text-[14px] leading-[1.95]">{c.text}</p>
                  </article>
                ))}
              </div>
            </>
          )}
        </Panel>
      </div>
    </div>
  );
}
