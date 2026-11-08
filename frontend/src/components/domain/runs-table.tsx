"use client";

import { useRouter } from "next/navigation";
import { StatusBadge } from "@/components/domain/badges";
import { EmptyState, SkeletonRows } from "@/components/ui/feedback";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useI18n } from "@/lib/i18n";
import type { Run } from "@/lib/types";

export function RunsTable({ runs }: { runs?: Run[] }) {
  const { t, pick, fmtDate, fmtNum } = useI18n();
  const router = useRouter();
  return (
    <div className="rounded-xl border border-line bg-surface">
      {!runs ? <SkeletonRows className="p-5" /> : runs.length === 0 ? <EmptyState title={t.assess.noRuns} /> : (
        <Table>
          <thead><tr><Th>{t.apps.company}</Th><Th>{t.common.status}</Th><Th>{t.assess.triggeredBy}</Th><Th className="text-end">{t.assess.duration}</Th><Th className="text-end">{t.assess.toolCalls}</Th><Th>{t.gov.provider}</Th><Th>{t.common.date}</Th></tr></thead>
          <tbody>
            {runs.map((r) => (
              <Tr key={r.id} onClick={() => router.push(`/agents/runs/${r.id}`)}>
                <Td><span className="font-medium">{pick(r.company_name_ar, r.company_name_en)}</span><p className="ltr text-start text-[12px] text-muted">{r.application_reference}</p></Td>
                <Td><StatusBadge status={r.status} group="runStatus" /></Td>
                <Td className="text-ink-2">{pick(r.triggered_by_name_ar, r.triggered_by_name_en)}</Td>
                <Td className="text-end num">{fmtNum(r.duration_ms / 1000, { maximumFractionDigits: 2 })} {t.common.sec}</Td>
                <Td className="text-end num">{fmtNum(r.tool_call_count)}</Td>
                <Td><span className="ltr text-[12.5px] text-muted">{r.ai_provider} / {r.tool_transport}</span></Td>
                <Td className="whitespace-nowrap text-ink-2">{fmtDate(r.created_at, true)}</Td>
              </Tr>
            ))}
          </tbody>
        </Table>
      )}
    </div>
  );
}
