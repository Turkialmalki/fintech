"use client";

import { useQuery } from "@tanstack/react-query";
import { ClipboardCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { OriginTag, RiskBadge, StatusBadge } from "@/components/domain/badges";
import { Segmented } from "@/components/ui/field";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/layout";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

type Item = { id: string; version: number; status: string; overall_risk: string; authored_by: string; finding_count: number; high_count: number;
  unverified_citations: number; application_reference: string; company_name_ar: string; company_name_en: string; service_category: string; created_at: string };

export default function Reviews() {
  const { t, pick, label, fmtNum, fmtRelative } = useI18n();
  const [status, setStatus] = useState("PENDING_REVIEW");
  const q = useQuery({ queryKey: ["queue", status], queryFn: () => api<Item[]>("/reviews/queue", { query: { status } }) });
  return (
    <div>
      <PageHeader title={t.reviews.title} subtitle={t.reviews.subtitle}
        actions={<Segmented value={status} onChange={setStatus} options={[
          { value: "PENDING_REVIEW", label: t.reviews.pending }, { value: "RETURNED", label: t.reviews.returned },
          { value: "APPROVED_FOR_NEXT_STAGE", label: t.reviews.approved }, { value: "REJECTED", label: t.reviews.rejected }]} />} />
      {q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : !q.data ? <SkeletonRows /> :
        q.data.length === 0 ? <EmptyState icon={ClipboardCheck} title={t.reviews.empty} hint={t.reviews.emptyHint} className="rounded-xl border border-line bg-surface" /> : (
          <ul className="flex flex-col gap-3">
            {q.data.map((d) => (
              <li key={d.id}>
                <Link href={`/reviews/${d.id}`} className="grid gap-4 rounded-xl border border-line bg-surface px-5 py-4 hover:border-primary/40 md:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,0.6fr))] md:items-center">
                  <div className="min-w-0">
                    <p className="text-[14.5px] font-semibold">{pick(d.company_name_ar, d.company_name_en)}</p>
                    <p className="mt-0.5 flex flex-wrap items-center gap-x-2.5 text-[12.5px] text-muted">
                      <span className="ltr">{d.application_reference}</span><span>{label("category", d.service_category)}</span>
                      <span>{t.assess.versionN} <span className="num">{d.version}</span></span><span>{fmtRelative(d.created_at)}</span>
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2"><StatusBadge status={d.status} group="draftStatus" /><OriginTag origin={d.authored_by} /></div>
                  </div>
                  <div><p className="text-[12px] text-muted">{t.assess.overallRisk}</p><div className="mt-1"><RiskBadge value={d.overall_risk} /></div></div>
                  <div><p className="text-[12px] text-muted">{t.reviews.high}</p><p className="mt-0.5 text-[18px] font-semibold num">{fmtNum(d.high_count)} <span className="text-[12.5px] font-normal text-muted">/ {fmtNum(d.finding_count)}</span></p></div>
                  <div><p className="text-[12px] text-muted">{t.reviews.unverified}</p><p className={`mt-0.5 text-[18px] font-semibold num ${d.unverified_citations ? "text-warning" : "text-success"}`}>{fmtNum(d.unverified_citations)}</p></div>
                </Link>
              </li>
            ))}
          </ul>
        )}
    </div>
  );
}
