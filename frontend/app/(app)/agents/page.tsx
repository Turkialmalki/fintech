"use client";

import { useQuery } from "@tanstack/react-query";
import { Bot, Hand } from "lucide-react";
import { RunsTable } from "@/components/domain/runs-table";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { PageHeader, Panel } from "@/components/ui/layout";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Run } from "@/lib/types";

type Graph = { nodes: string[]; agents: Record<string, string[]> };
type Settings = { runtime: Record<string, number> };
const NODE_AGENT: Record<string, string> = { start: "orchestrator", human_review_checkpoint: "orchestrator" };

export default function Agents() {
  const { t, fmtNum } = useI18n();
  const g = useQuery({ queryKey: ["graph"], queryFn: () => api<Graph>("/agents/graph") });
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api<Run[]>("/assessments/runs") });
  const budget = runs.data?.[0]?.budget;
  const names = t.agents.names as Record<string, string>;
  const desc = t.agents.descriptions as Record<string, string>;

  return (
    <div>
      <PageHeader title={t.agents.title} subtitle={t.agents.subtitle} />
      {g.isError ? <ErrorState error={g.error} /> : (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <Panel title={t.agents.workflow}>
            {!g.data ? <Skeleton className="h-80" /> : (
              <ol className="relative flex flex-col">
                {g.data.nodes.map((n, i) => {
                  const agent = NODE_AGENT[n] ?? n;
                  const human = n === "human_review_checkpoint";
                  return (
                    <li key={n} className="relative flex gap-4 pb-5 last:pb-0">
                      {i < g.data.nodes.length - 1 && <span className="absolute start-[17px] top-9 h-[calc(100%-28px)] w-px bg-line-strong" aria-hidden />}
                      <span className={`z-10 grid size-9 shrink-0 place-items-center rounded-full border ${human ? "border-warning-base bg-warning-soft text-warning" : "border-line-strong bg-surface text-ink-2"}`}>
                        {human ? <Hand className="size-4" /> : <span className="text-[12.5px] font-semibold num">{i + 1}</span>}
                      </span>
                      <div className="min-w-0 flex-1 pt-1">
                        <p className="text-[14px] font-semibold">{human ? t.agents.humanCheckpoint : names[agent]}</p>
                        <p className="mt-0.5 text-[13px] text-muted">{human ? t.agents.humanCheckpointHint : n === "start" ? desc.orchestrator : desc[agent]}</p>
                        {!human && n !== "start" && (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {(g.data.agents[agent] ?? []).map((tool) => <code key={tool} className="ltr rounded bg-surface-2 px-1.5 py-0.5 text-[11.5px] text-ink-2">{tool}</code>)}
                          </div>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
          </Panel>
          <div className="flex flex-col gap-6">
            <Panel title={t.agents.budget} description={t.agents.subtitle}>
              {!budget ? <Skeleton className="h-28" /> : (
                <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
                  {[[t.agents.maxSteps, budget.max_steps, budget.used_steps], [t.agents.maxTools, budget.max_tool_calls, budget.used_tool_calls],
                    [t.agents.tokenBudget, budget.max_tokens, budget.used_tokens], [t.agents.timeout, budget.timeout_s, budget.elapsed_s]].map(([l, max, used]) => (
                    <div key={String(l)}>
                      <dt className="text-[12px] text-muted">{l}</dt>
                      <dd className="mt-0.5 text-[16px] font-semibold num">{fmtNum(Number(max))}</dd>
                      <dd className="text-[11.5px] text-muted">{t.agents.used} <span className="num">{fmtNum(Number(used), { maximumFractionDigits: 2 })}</span></dd>
                    </div>
                  ))}
                </dl>
              )}
            </Panel>
            <Panel title={t.agents.tools}>
              <p className="flex items-start gap-2 text-[13px] leading-relaxed text-ink-2"><Bot className="mt-0.5 size-4 shrink-0 text-muted" />
                {t.mcp.subtitle}</p>
            </Panel>
          </div>
        </div>
      )}
      <h2 className="mb-3 mt-8 text-[15px] font-semibold">{t.agents.recentRuns}</h2>
      <RunsTable runs={runs.data} />
    </div>
  );
}
