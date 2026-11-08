"use client";

import { useQuery } from "@tanstack/react-query";
import { FileStack, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { RiskBadge, StatusBadge } from "@/components/domain/badges";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/field";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/layout";
import { Pagination, Table, Td, Th, Tr } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { labels } from "@/lib/dictionaries";
import { useI18n } from "@/lib/i18n";
import type { Application, Page } from "@/lib/types";
import { cn } from "@/lib/utils";

function useDebounced<T>(v: T, ms = 300) {
  const [d, setD] = useState(v);
  useEffect(() => { const h = setTimeout(() => setD(v), ms); return () => clearTimeout(h); }, [v, ms]);
  return d;
}

function ApplicationsList() {
  const { t, label, pick, fmtDate } = useI18n();
  const { can } = useAuth();
  const router = useRouter();
  const sp = useSearchParams();
  const [status, setStatus] = useState(sp.get("status") ?? "");
  const [category, setCategory] = useState("");
  const [q, setQ] = useState("");
  const [mine, setMine] = useState(false);
  const [page, setPage] = useState(1);
  const dq = useDebounced(q);
  useEffect(() => setPage(1), [status, category, dq, mine]);
  const res = useQuery({
    queryKey: ["applications", status, category, dq, mine, page],
    queryFn: () => api<Page<Application>>("/applications", { query: { status: status || undefined, category: category || undefined, q: dq, mine: mine || undefined, page, page_size: 15 } }),
    placeholderData: (p) => p,
  });

  return (
    <div>
      <PageHeader title={t.apps.title} subtitle={t.apps.subtitle}
        actions={can("applications:write") && <Button asChild><Link href="/applications/new"><Plus />{t.apps.new}</Link></Button>} />

      <div className="rounded-xl border border-line bg-surface">
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3.5">
          <div className="relative min-w-[240px] flex-1">
            <Search className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t.apps.searchPlaceholder} aria-label={t.common.search} className="ps-9" />
          </div>
          <Select aria-label={t.common.status} value={status} onChange={(e) => setStatus(e.target.value)} className="min-w-48">
            <option value="">{pick("كل الحالات", "All statuses")}</option>
            {Object.keys(labels.status).map((s) => <option key={s} value={s}>{label("status", s)}</option>)}
          </Select>
          <Select aria-label={t.apps.category} value={category} onChange={(e) => setCategory(e.target.value)} className="min-w-44">
            <option value="">{pick("كل الفئات", "All categories")}</option>
            {Object.keys(labels.category).map((c) => <option key={c} value={c}>{label("category", c)}</option>)}
          </Select>
          <button type="button" aria-pressed={mine} onClick={() => setMine(!mine)}
            className={cn("h-9 rounded-md border px-3 text-[13px] font-medium", mine ? "border-primary bg-primary-soft text-primary" : "border-line-strong text-ink-2 hover:bg-surface-2")}>
            {t.apps.mine}
          </button>
        </div>

        {res.isError ? <ErrorState error={res.error} onRetry={() => res.refetch()} /> : !res.data ? <SkeletonRows className="p-5" rows={8} /> :
          res.data.items.length === 0 ? <EmptyState icon={FileStack} title={t.apps.empty} hint={t.apps.emptyHint} /> : (
            <>
              <Table>
                <thead><tr>
                  <Th>{t.apps.company}</Th><Th>{t.apps.category}</Th><Th>{t.common.status}</Th><Th>{t.apps.risk}</Th>
                  <Th>{t.apps.analyst}</Th><Th className="text-end">{t.apps.documents}</Th><Th>{t.apps.created}</Th>
                </tr></thead>
                <tbody>
                  {res.data.items.map((a) => (
                    <Tr key={a.id} onClick={() => router.push(`/applications/${a.id}`)}>
                      <Td>
                        <Link href={`/applications/${a.id}`} onClick={(e) => e.stopPropagation()} className="font-medium text-ink hover:text-primary">{pick(a.company_name_ar, a.company_name_en)}</Link>
                        <p className="ltr mt-0.5 text-[12px] text-muted text-start">{a.reference}</p>
                      </Td>
                      <Td className="text-ink-2">{label("category", a.service_category)}</Td>
                      <Td><StatusBadge status={a.status} /></Td>
                      <Td><RiskBadge value={a.latest_risk} /></Td>
                      <Td className="text-ink-2">{pick(a.assigned_analyst_name_ar, a.assigned_analyst_name_en) ?? <span className="text-faint">{t.apps.unassigned}</span>}</Td>
                      <Td className="text-end num">{a.document_count}</Td>
                      <Td className="whitespace-nowrap text-ink-2">{fmtDate(a.created_at)}</Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
              <Pagination page={page} pageSize={15} total={res.data.total} onPage={setPage} />
            </>
          )}
      </div>
      <p className="mt-3 text-[12px] text-muted">{t.apps.workflowNote}</p>
    </div>
  );
}

export default function Page() {
  return <Suspense><ApplicationsList /></Suspense>;
}
