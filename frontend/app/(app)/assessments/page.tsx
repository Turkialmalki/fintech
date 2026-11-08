"use client";

import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { RiskBadge, StatusBadge } from "@/components/domain/badges";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/feedback";
import { PageHeader, TabPanel, Tabs } from "@/components/ui/layout";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Run } from "@/lib/types";
import { RunsTable } from "@/components/domain/runs-table";

type QueueItem = { id: string; version: number; status: string; overall_risk: string; finding_count: number; high_count: number; unverified_citations: number;
  application_reference: string; company_name_ar: string; company_name_en: string; service_category: string; created_at: string; authored_by: string };

export default function Assessments() {
  const { t, pick, fmtDate, fmtNum, label } = useI18n();
  const router = useRouter();
  const [tab, setTab] = useState("drafts");
  const drafts = useQuery({ queryKey: ["all-drafts"], queryFn: () => api<QueueItem[]>("/reviews/queue", { query: { status: "DRAFT,PENDING_REVIEW,RETURNED,APPROVED_FOR_NEXT_STAGE,REJECTED" } }) });
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api<Run[]>("/assessments/runs") });
  return (
    <div>
      <PageHeader title={t.assess.title} subtitle={t.assess.subtitle} />
      <Tabs value={tab} onValueChange={setTab} items={[{ value: "drafts", label: t.assess.drafts, count: drafts.data?.length }, { value: "runs", label: t.assess.runs, count: runs.data?.length }]}>
        <TabPanel value="drafts">
          <div className="rounded-xl border border-line bg-surface">
            {drafts.isError ? <ErrorState error={drafts.error} /> : !drafts.data ? <SkeletonRows className="p-5" /> : drafts.data.length === 0 ? <EmptyState icon={Sparkles} title={t.assess.noRuns} /> : (
              <Table>
                <thead><tr><Th>{t.apps.company}</Th><Th>{t.common.status}</Th><Th>{t.assess.overallRisk}</Th><Th className="text-end">{t.assess.findings}</Th><Th className="text-end">{t.reviews.high}</Th><Th>{t.common.date}</Th></tr></thead>
                <tbody>
                  {drafts.data.map((d) => (
                    <Tr key={d.id} onClick={() => router.push(`/assessments/${d.id}`)}>
                      <Td><Link href={`/assessments/${d.id}`} className="font-medium hover:text-primary" onClick={(e) => e.stopPropagation()}>{pick(d.company_name_ar, d.company_name_en)}</Link>
                        <p className="text-[12px] text-muted"><span className="ltr">{d.application_reference}</span> · {label("category", d.service_category)} · {t.assess.versionN} <span className="num">{d.version}</span></p></Td>
                      <Td><StatusBadge status={d.status} group="draftStatus" /></Td>
                      <Td><RiskBadge value={d.overall_risk} /></Td>
                      <Td className="text-end num">{fmtNum(d.finding_count)}</Td>
                      <Td className="text-end num">{fmtNum(d.high_count)}</Td>
                      <Td className="whitespace-nowrap text-ink-2">{fmtDate(d.created_at, true)}</Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            )}
          </div>
        </TabPanel>
        <TabPanel value="runs"><RunsTable runs={runs.data} /></TabPanel>
      </Tabs>
    </div>
  );
}
