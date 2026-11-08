"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Run } from "@/lib/types";

const ORDER = ["orchestrator", "document_intelligence", "regulatory_research", "compliance_gap", "risk_analysis", "assessment_reporting"];

/** Live view of an agent run: polls until it reaches a terminal state. */
export function RunProgress({ runId, applicationId }: { runId: string; applicationId?: string }) {
  const { t, fmtNum } = useI18n();
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["run", runId], queryFn: () => api<Run>(`/assessments/runs/${runId}`),
    refetchInterval: (query) => (["QUEUED", "RUNNING"].includes(query.state.data?.status ?? "QUEUED") ? 800 : false),
  });
  const run = q.data;
  const done = run && !["QUEUED", "RUNNING"].includes(run.status);
  useEffect(() => {
    if (done) {
      qc.invalidateQueries({ queryKey: ["application", applicationId] });
      qc.invalidateQueries({ queryKey: ["app-assessments", applicationId] });
      qc.invalidateQueries({ queryKey: ["events", applicationId] });
    }
  }, [done, qc, applicationId]);
  const agentsSeen = new Set(run?.steps?.map((s) => s.agent));
  const failed = run?.status === "FAILED";
  return (
    <div className="rounded-xl border border-line bg-surface p-5" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-[14px] font-medium">
          {!done ? <Loader2 className="size-4 animate-spin text-primary" /> : failed ? <XCircle className="size-4 text-danger" /> : <CheckCircle2 className="size-4 text-success" />}
          {!done ? t.assess.running : failed ? t.assess.runFailed : t.assess.pendingReview}
        </p>
        <p className="text-[12.5px] text-muted num">{fmtNum(run?.step_count ?? 0)} {t.assess.steps} · {fmtNum(run?.tool_call_count ?? 0)} {t.assess.toolCalls}</p>
      </div>
      <ol className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {ORDER.map((a, i) => {
          const reached = agentsSeen.has(a) || (done && !failed);
          return (
            <li key={a} className={`rounded-md border px-3 py-2 text-[12px] ${reached ? "border-primary/30 bg-primary-soft/40 text-ink" : "border-line text-muted"}`}>
              <span className="num me-1 text-faint">{i + 1}</span>{(t.agents.names as Record<string, string>)[a]}
            </li>
          );
        })}
      </ol>
      {failed && <p className="mt-3 text-[12.5px] text-danger ltr text-start">{run?.error}</p>}
      {done && (
        <div className="mt-4 flex gap-3 text-[13px]">
          {run?.final_state?.draft_id && <Link className="font-medium text-primary hover:underline" href={`/assessments/${run.final_state.draft_id}`}>{t.apps.openWorkspace}</Link>}
          <Link className="text-ink-2 hover:underline" href={`/agents/runs/${runId}`}>{t.agents.viewRun}</Link>
        </div>
      )}
    </div>
  );
}
