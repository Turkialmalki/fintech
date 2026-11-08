"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Bot, Brain, Flag, Wrench } from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";
import { MockTag, StatusBadge } from "@/components/domain/badges";
import { Segmented } from "@/components/ui/field";
import { ErrorState, SkeletonRows } from "@/components/ui/feedback";
import { DescList, PageHeader, Panel } from "@/components/ui/layout";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Run } from "@/lib/types";
import { cn } from "@/lib/utils";

const ICON: Record<string, React.ElementType> = { NODE: Bot, TOOL_CALL: Wrench, LLM_CALL: Brain, DECISION: Flag, ERROR: AlertTriangle };

export default function RunViewer({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t, pick, fmtNum, fmtDate } = useI18n();
  const [filter, setFilter] = useState("ALL");
  const [open, setOpen] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["run", id], queryFn: () => api<Run>(`/assessments/runs/${id}`),
    refetchInterval: (qq) => (["QUEUED", "RUNNING"].includes(qq.state.data?.status ?? "") ? 1000 : false) });
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const r = q.data;
  if (!r) return <SkeletonRows rows={10} />;
  const steps = (r.steps ?? []).filter((s) => filter === "ALL" || s.step_type === filter);
  const names = t.agents.names as Record<string, string>;
  const types = t.agents.stepTypes as Record<string, string>;
  return (
    <div>
      <PageHeader title={t.agents.timeline} crumbs={[{ label: t.agents.title, href: "/agents" }, { label: r.id.slice(0, 8) }]}
        meta={<><StatusBadge status={r.status} group="runStatus" /><span className="ltr text-[12.5px] text-muted">{r.ai_provider} · {r.ai_model} · {r.tool_transport}</span><MockTag show={r.ai_provider === "mock"} /></>}
        actions={r.final_state?.draft_id && <Link className="text-[13px] font-medium text-primary hover:underline" href={`/assessments/${r.final_state.draft_id}`}>{t.apps.openWorkspace}</Link>} />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(280px,0.8fr)]">
        <Panel title={t.agents.timeline} bodyClass="p-0" actions={<Segmented size="sm" value={filter} onChange={setFilter}
          options={[{ value: "ALL", label: t.common.all }, ...["NODE", "TOOL_CALL", "LLM_CALL"].map((v) => ({ value: v, label: types[v] }))]} />}>
          <ol className="divide-y divide-line">
            {steps.map((s) => {
              const Icon = ICON[s.step_type] ?? Bot;
              const isOpen = open === s.id;
              return (
                <li key={s.id}>
                  <button type="button" onClick={() => setOpen(isOpen ? null : s.id)} aria-expanded={isOpen} className="flex w-full items-center gap-3 px-5 py-2.5 text-start hover:bg-canvas">
                    <span className="w-7 text-[11.5px] text-faint num">{s.sequence}</span>
                    <Icon className={cn("size-4 shrink-0", s.status !== "OK" ? "text-danger" : s.step_type === "TOOL_CALL" ? "text-primary" : s.step_type === "LLM_CALL" ? "text-accent" : "text-muted")} />
                    <span className="min-w-0 flex-1">
                      <span className="ltr me-2 text-[13px] font-medium">{s.name}</span>
                      <span className="text-[12px] text-muted">{names[s.agent] ?? s.agent} · {types[s.step_type]}</span>
                    </span>
                    {s.status !== "OK" && <span className="text-[12px] text-danger">{s.status}</span>}
                    <span className="text-[12px] text-muted num">{fmtNum(s.duration_ms)} {t.common.ms}</span>
                  </button>
                  {isOpen && (
                    <div className="grid gap-3 bg-canvas px-5 pb-4 pt-1 md:grid-cols-2">
                      {[[t.agents.input, s.input], [t.agents.output, s.output]].map(([l, v]) => (
                        <div key={String(l)}>
                          <p className="mb-1 text-[12px] font-medium text-muted">{String(l)}</p>
                          <pre dir="ltr" className="max-h-72 overflow-auto rounded-md border border-line bg-surface p-3 text-[11.5px] leading-relaxed scroll-thin">{JSON.stringify(v, null, 2)}</pre>
                        </div>
                      ))}
                      {s.error && <p className="ltr text-[12px] text-danger md:col-span-2">{s.error}</p>}
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        </Panel>
        <div className="flex flex-col gap-6">
          <Panel title={t.common.details}>
            <DescList cols={1} items={[
              { label: t.assess.triggeredBy, value: pick(r.triggered_by_name_ar, r.triggered_by_name_en) },
              { label: t.common.date, value: fmtDate(r.created_at, true) },
              { label: t.assess.duration, value: <span className="num">{fmtNum(r.duration_ms)} {t.common.ms}</span> },
              { label: t.assess.steps, value: <span className="num">{fmtNum(r.step_count)}</span> },
              { label: t.assess.toolCalls, value: <span className="num">{fmtNum(r.tool_call_count)}</span> },
              { label: t.dashboard.tokens, value: <span className="num">{fmtNum(r.tokens_in + r.tokens_out)}</span> },
              { label: t.audit.cost, value: <span className="num">${fmtNum(r.cost_usd, { maximumFractionDigits: 4 })}</span> },
            ]} />
            {r.error && <p className="ltr mt-4 rounded-md bg-danger-soft p-3 text-[12px] text-danger">{r.error}</p>}
          </Panel>
          <Panel title={t.agents.budget}>
            <DescList cols={1} items={Object.entries(r.budget ?? {}).map(([k, v]) => ({ label: k.replaceAll("_", " "), value: <span className="num">{fmtNum(Number(v), { maximumFractionDigits: 2 })}</span> }))} />
          </Panel>
        </div>
      </div>
    </div>
  );
}
