"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { BadgeCheck, CircleDashed, ScanSearch, ShieldAlert, SlidersHorizontal, Sparkles } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { MockTag } from "@/components/domain/badges";
import { SourceDrawer } from "@/components/domain/evidence";
import { Button } from "@/components/ui/button";
import { Checkbox, Field, Input, Segmented, Select } from "@/components/ui/field";
import { EmptyState, ErrorState, Notice, Skeleton } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/layout";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Hit } from "@/lib/types";
import { cn } from "@/lib/utils";

type RagCitation = { source_id: string; quote: string; verified: boolean; chunk_id: string | null; document_code: string | null; page_number: number | null; section: string | null; version_label: string | null };
type RagResult = {
  insufficient_evidence: boolean; evidence_summary: string; interpretation: string; citations: RagCitation[]; citation_accuracy: number | null;
  sources: Hit[]; retrieval: Record<string, any>; is_mock: boolean; message_ar?: string; message_en?: string;
  document_injection_flags?: Record<string, string[]>; query_injection_flags?: string[];
};
type SearchResult = { results: Hit[]; meta: Record<string, any> };
type RegDoc = { id: string; document_code: string; title_ar: string; title_en: string };

function Relevance({ score }: { score: number }) {
  const { t, fmtNum } = useI18n();
  const pct = Math.round(Math.min(1, Math.max(0, score)) * 100);
  return (
    <span className="inline-flex items-center gap-2 text-[12px] text-muted" title={`${t.intel.relevance} ${pct}%`}>
      <span className="h-1.5 w-14 overflow-hidden rounded-full bg-surface-2"><span className="block h-full rounded-full bg-primary" style={{ width: `${pct}%` }} /></span>
      <span className="num">{fmtNum(pct)}%</span>
    </span>
  );
}

/** Renders [S1] markers in answer text as numbered chips that open the source. */
function AnswerText({ text, onCite }: { text: string; onCite: (sid: string) => void }) {
  const parts = text.split(/(\[S\d+\])/g);
  return (
    <p className="whitespace-pre-line text-[15px] leading-[1.95] text-ink">
      {parts.map((p, i) => {
        const m = p.match(/^\[S(\d+)\]$/);
        if (!m) return <span key={i}>{p}</span>;
        return <button key={i} type="button" onClick={() => onCite(`S${m[1]}`)}
          className="mx-0.5 inline-grid size-[20px] place-items-center rounded-full bg-ink align-[2px] text-[10.5px] font-semibold text-white hover:bg-primary num">{m[1]}</button>;
      })}
    </p>
  );
}

function Intelligence() {
  const { t, pick, fmtNum, fmtDate, locale } = useI18n();
  const sp = useSearchParams();
  const [query, setQuery] = useState(sp.get("q") ?? "");
  const [kind, setKind] = useState<"answer" | "search">("answer");
  const [showFilters, setShowFilters] = useState(false);
  const [f, setF] = useState({ mode: "hybrid", document_ids: "", language: "", section: "", include_superseded: false, published_from: "", effective_from: "", rerank: true });
  const [source, setSource] = useState<{ chunk: string; quote?: string } | null>(null);
  const docs = useQuery({ queryKey: ["regdocs"], queryFn: () => api<{ items: RegDoc[] }>("/regulatory/documents") });

  const body = () => ({ query, mode: f.mode, top_k: 8, rerank: f.rerank, document_ids: f.document_ids ? [f.document_ids] : [], language: f.language,
    section: f.section, include_superseded: f.include_superseded, published_from: f.published_from || null, effective_from: f.effective_from || null, locale });
  const rag = useMutation({ mutationFn: () => api<RagResult>("/rag/query", { body: body() }) });
  const search = useMutation({ mutationFn: () => api<SearchResult>("/regulatory/search", { body: body() }) });
  const active = kind === "answer" ? rag : search;
  const submit = () => { if (query.trim().length >= 2) active.mutate(); };
  useEffect(() => { if (sp.get("q")) rag.mutate(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const hits: Hit[] = kind === "answer" ? rag.data?.sources ?? [] : search.data?.results ?? [];
  const meta = kind === "answer" ? rag.data?.retrieval : search.data?.meta;
  const openCite = (sid: string) => {
    const c = rag.data?.citations.find((x) => x.source_id === sid);
    const idx = Number(sid.slice(1)) - 1;
    const chunk = c?.chunk_id ?? rag.data?.sources[idx]?.chunk_id;
    if (chunk) setSource({ chunk, quote: c?.quote });
  };

  return (
    <div>
      <PageHeader title={t.intel.title} subtitle={t.intel.subtitle} meta={<MockTag show={!!rag.data?.is_mock} />} />

      <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="rounded-xl border border-line bg-surface p-2 focus-within:border-primary focus-within:ring-[3px] focus-within:ring-primary/10">
        <div className="flex items-center gap-2">
          <ScanSearch className="ms-3 size-5 shrink-0 text-muted" aria-hidden />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t.intel.placeholder} aria-label={t.common.search} dir="auto"
            className="h-12 min-w-0 flex-1 bg-transparent text-[15.5px] placeholder:text-faint focus:outline-none" />
          <Button type="submit" size="lg" loading={active.isPending} disabled={query.trim().length < 2}>
            {kind === "answer" ? <Sparkles /> : <ScanSearch />}{kind === "answer" ? t.intel.ask : t.intel.searchOnly}
          </Button>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-2 pt-2">
          <Segmented size="sm" value={kind} onChange={setKind} options={[{ value: "answer", label: t.intel.ask }, { value: "search", label: t.intel.searchOnly }]} />
          <Button type="button" variant="ghost" size="sm" aria-expanded={showFilters} onClick={() => setShowFilters(!showFilters)}><SlidersHorizontal />{t.common.filters}</Button>
        </div>
        {showFilters && (
          <div className="grid gap-4 border-t border-line p-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label={t.intel.mode}><Select value={f.mode} onChange={(e) => setF({ ...f, mode: e.target.value })}>
              <option value="hybrid">{t.intel.hybrid}</option><option value="keyword">{t.intel.keyword}</option><option value="semantic">{t.intel.semantic}</option></Select></Field>
            <Field label={t.intel.document}><Select value={f.document_ids} onChange={(e) => setF({ ...f, document_ids: e.target.value })}>
              <option value="">{t.intel.allDocs}</option>{docs.data?.items.map((d) => <option key={d.id} value={d.id}>{d.document_code} — {pick(d.title_ar, d.title_en)}</option>)}</Select></Field>
            <Field label={t.intel.language}><Select value={f.language} onChange={(e) => setF({ ...f, language: e.target.value })}>
              <option value="">{t.common.all}</option><option value="ar">العربية</option><option value="en">English</option></Select></Field>
            <Field label={t.intel.section}><Input value={f.section} placeholder={t.intel.sectionPlaceholder} onChange={(e) => setF({ ...f, section: e.target.value })} /></Field>
            <Field label={t.intel.publishedFrom}><Input type="date" value={f.published_from} onChange={(e) => setF({ ...f, published_from: e.target.value })} /></Field>
            <Field label={t.intel.effectiveFrom}><Input type="date" value={f.effective_from} onChange={(e) => setF({ ...f, effective_from: e.target.value })} /></Field>
            <div className="flex flex-col justify-end gap-2 pb-1 lg:col-span-2">
              <Checkbox label={t.intel.includeSuperseded} checked={f.include_superseded} onChange={(v) => setF({ ...f, include_superseded: v })} />
              <Checkbox label={t.intel.rerank} checked={f.rerank} onChange={(v) => setF({ ...f, rerank: v })} />
            </div>
          </div>
        )}
      </form>

      {!active.data && !active.isPending && !active.isError && (
        <div className="mt-8">
          <EmptyState icon={ScanSearch} title={t.intel.emptyTitle} hint={t.intel.emptyHint} />
          <ul className="mx-auto -mt-4 flex max-w-3xl flex-wrap justify-center gap-2">
            {t.intel.suggestions.map((s) => (
              <li key={s}><button type="button" dir="auto" onClick={() => { setQuery(s); setTimeout(() => active.mutate(), 0); }}
                className="rounded-full border border-line bg-surface px-3.5 py-1.5 text-[13px] text-ink-2 hover:border-primary/40 hover:text-ink">{s}</button></li>
            ))}
          </ul>
        </div>
      )}
      {active.isError && <ErrorState error={active.error} onRetry={submit} />}
      {active.isPending && <div className="mt-6 grid gap-4"><Skeleton className="h-32" /><Skeleton className="h-24" /><Skeleton className="h-24" /></div>}

      {active.data && !active.isPending && (
        <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
          {kind === "answer" && rag.data && (
            <section className="order-1 rounded-xl border border-line bg-surface p-6 xl:order-none">
              {rag.data.insufficient_evidence ? (
                <div className="flex items-start gap-3">
                  <CircleDashed className="mt-1 size-5 text-warning" />
                  <div><p className="text-[15px] font-medium">{t.intel.insufficient}</p>
                    <p className="mt-1 text-[13.5px] text-muted">{pick(rag.data.message_ar, rag.data.message_en)}</p></div>
                </div>
              ) : (
                <>
                  <p className="text-[12.5px] font-medium text-muted">{t.intel.evidence}</p>
                  <div className="mt-2"><AnswerText text={rag.data.evidence_summary} onCite={openCite} /></div>
                  <div className="mt-6 border-t border-line pt-4">
                    <p className="text-[12.5px] font-medium text-muted">{t.intel.interpretation}</p>
                    <p className="mt-1.5 text-[14px] leading-relaxed text-ink-2">{rag.data.interpretation}</p>
                  </div>
                  <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-line pt-4 text-[12.5px] text-muted">
                    <span>{t.intel.citationAccuracy}: <span className="font-medium text-ink num">{rag.data.citation_accuracy != null ? fmtNum(rag.data.citation_accuracy, { style: "percent" }) : "—"}</span></span>
                    {rag.data.citations.map((c) => (
                      <button key={c.source_id + c.quote.slice(0, 10)} type="button" onClick={() => openCite(c.source_id)} className={cn("inline-flex items-center gap-1", c.verified ? "text-success" : "text-warning")}>
                        {c.verified ? <BadgeCheck className="size-3.5" /> : <CircleDashed className="size-3.5" />}
                        <span className="num">{c.source_id.slice(1)}</span> <span className="ltr">{c.document_code}</span>
                      </button>
                    ))}
                  </div>
                </>
              )}
              {rag.data.document_injection_flags && Object.keys(rag.data.document_injection_flags).length > 0 &&
                <Notice tone="warning" icon={ShieldAlert} className="mt-4">{t.intel.injection}</Notice>}
            </section>
          )}

          <section className={cn("min-w-0", kind === "search" && "xl:col-span-2")} aria-label={t.intel.sources}>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-[14.5px] font-semibold">{t.intel.sources} <span className="text-muted num">({fmtNum(hits.length)})</span></h2>
              {meta && <p className="text-[12px] text-muted num">{t.intel.latency} {fmtNum(meta.latency_ms)} {t.common.ms} · {t.intel.keywordHits} {fmtNum(meta.keyword_hits)} · {t.intel.vectorHits} {fmtNum(meta.vector_hits)}</p>}
            </div>
            {hits.length === 0 ? <EmptyState title={t.intel.insufficient} /> : (
              <ol className={cn("grid grid-cols-[minmax(0,1fr)] gap-3", kind === "search" && "lg:grid-cols-[repeat(2,minmax(0,1fr))]")}>
                {hits.map((h, i) => (
                  <li key={h.chunk_id} className="min-w-0">
                    <button type="button" onClick={() => setSource({ chunk: h.chunk_id })}
                      className="flex w-full flex-col gap-2 rounded-xl border border-line bg-surface p-4 text-start hover:border-primary/40">
                      <div className="flex w-full items-start justify-between gap-3">
                        <div className="flex min-w-0 items-start gap-2.5">
                          {kind === "answer" && <span className="mt-0.5 grid size-[20px] shrink-0 place-items-center rounded-full bg-ink text-[10.5px] font-semibold text-white num">{i + 1}</span>}
                          <div className="min-w-0">
                            <p className="truncate text-[13.5px] font-medium">{pick(h.title_ar, h.title_en) || h.document_code}</p>
                            <p className="mt-0.5 flex flex-wrap gap-x-2.5 text-[12px] text-muted">
                              <span className="ltr">{h.document_code} v{h.version_label}</span><span>{h.section}</span>
                              <span>{h.page_number ? `${t.intel.page} ${h.page_number}` : t.intel.noPage}</span>
                              {h.version_status !== "ACTIVE" && <span className="text-warning">{t.intel.superseded}</span>}
                            </p>
                          </div>
                        </div>
                        <Relevance score={h.score} />
                      </div>
                      <p dir="auto" className="line-clamp-4 text-[13.5px] leading-[1.85] text-ink-2">{h.text}</p>
                      <p className="flex flex-wrap gap-x-3 text-[11.5px] text-faint">
                        {h.is_synthetic && <span className="text-warning">{t.kb.synthetic}</span>}
                        {h.effective_date && <span>{t.kb.effective}: {fmtDate(h.effective_date)}</span>}
                        <span>{(t.kb as Record<string, string>)[h.classification]}</span>
                      </p>
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>
      )}
      <SourceDrawer chunkId={source?.chunk ?? null} quote={source?.quote} open={!!source} onOpenChange={(o) => !o && setSource(null)} />
    </div>
  );
}

export default function Page() {
  return <Suspense><Intelligence /></Suspense>;
}
