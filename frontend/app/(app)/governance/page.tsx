"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/field";
import { EmptyState, ErrorState, Notice, SkeletonRows } from "@/components/ui/feedback";
import { PageHeader, Panel, TabPanel, Tabs } from "@/components/ui/layout";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { api, errorText } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

type UseCase = { id: string; code: string; name_ar: string; name_en: string; business_purpose_ar: string; business_purpose_en: string; owner: string; model_name: string | null;
  risk_classification: string; data_classification: string; human_oversight: string; approval_status: string; deployment_status: string; monitoring_status: string;
  control_mappings: { framework: string; control_ref: string; status: string; note: string }[] };
type Model = { id: string; name: string; provider: string; model_id: string; version: string; purpose: string; hosting: string; owner: string; approval_status: string;
  deployment_status: string; is_active: boolean; capabilities: Record<string, unknown>; capabilities_checked_at: string | null; notes: string; context_window: number | null };
type Control = { id: string; framework: string; reference: string; title_ar: string; title_en: string; description_ar: string; description_en: string };
type Eval = { id: string; created_at: string; provider: string; model_name: string; dataset: string; metrics: Record<string, any>; sample_count: number; is_mock: boolean };

const TONE: Record<string, "success" | "warning" | "neutral" | "danger" | "primary"> = {
  APPROVED: "success", PENDING: "warning", REJECTED: "danger", RETIRED: "neutral", PRODUCTION: "success", STAGING: "primary", NOT_DEPLOYED: "neutral",
  MONITORED: "success", DEGRADED: "danger", NOT_MONITORED: "neutral", MAPPED: "success", PARTIAL: "warning", PLANNED: "neutral", UNDER_REVIEW: "primary",
};

export default function Governance() {
  const { t, pick, label, fmtDate, fmtNum, locale } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState("usecases");
  const ucs = useQuery({ queryKey: ["usecases"], queryFn: () => api<UseCase[]>("/governance/use-cases") });
  const models = useQuery({ queryKey: ["models"], queryFn: () => api<Model[]>("/governance/models") });
  const controls = useQuery({ queryKey: ["controls"], queryFn: () => api<{ items: Control[] }>("/governance/controls") });
  const evals = useQuery({ queryKey: ["evals"], queryFn: () => api<Eval[]>("/governance/evaluations") });
  const runEval = useMutation({ mutationFn: () => api("/governance/evaluations/run", { method: "POST" }),
    onSuccess: () => { toast.success(t.gov.evalDone); qc.invalidateQueries({ queryKey: ["evals"] }); setTab("evaluations"); }, onError: (e) => toast.error(errorText(e, locale)) });
  const patchUc = useMutation({ mutationFn: ({ id, body }: { id: string; body: Record<string, string> }) => api(`/governance/use-cases/${id}`, { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["usecases"] }), onError: (e) => toast.error(errorText(e, locale)) });
  const manage = can("governance:manage");
  const fw = t.gov.frameworks as Record<string, string>;

  return (
    <div>
      <PageHeader title={t.gov.title} subtitle={t.gov.subtitle}
        actions={manage && <Button onClick={() => runEval.mutate()} loading={runEval.isPending}><FlaskConical />{runEval.isPending ? t.gov.evalRunning : t.gov.runEval}</Button>} />
      <Tabs value={tab} onValueChange={setTab} items={[{ value: "usecases", label: t.gov.useCases, count: ucs.data?.length }, { value: "models", label: t.gov.models, count: models.data?.length },
        { value: "evaluations", label: t.gov.evaluations, count: evals.data?.length }, { value: "controls", label: t.gov.controls }]}>
        <TabPanel value="usecases" className="flex flex-col gap-4">
          {ucs.isError ? <ErrorState error={ucs.error} /> : !ucs.data ? <SkeletonRows /> : ucs.data.map((u) => (
            <article key={u.id} className="rounded-xl border border-line bg-surface p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="ltr text-start text-[12px] text-muted">{u.code}</p>
                  <h3 className="text-[15px] font-semibold">{pick(u.name_ar, u.name_en)}</h3>
                  <p className="mt-1 max-w-2xl text-[13px] text-ink-2">{pick(u.business_purpose_ar, u.business_purpose_en)}</p>
                </div>
                <Badge tone={u.risk_classification === "HIGH" ? "danger" : u.risk_classification === "MEDIUM" ? "warning" : "success"}>{t.gov.riskClass}: {label("severity", u.risk_classification)}</Badge>
              </div>
              <dl className="mt-4 grid gap-4 border-t border-line pt-4 text-[13px] sm:grid-cols-3 lg:grid-cols-6">
                <div><dt className="text-[12px] text-muted">{t.gov.owner}</dt><dd>{u.owner}</dd></div>
                <div><dt className="text-[12px] text-muted">{t.gov.models}</dt><dd>{u.model_name}</dd></div>
                <div><dt className="text-[12px] text-muted">{t.gov.dataClass}</dt><dd className="ltr text-start">{u.data_classification}</dd></div>
                {(["approval_status", "deployment_status", "monitoring_status"] as const).map((f) => (
                  <div key={f}><dt className="text-[12px] text-muted">{f === "approval_status" ? t.gov.approval : f === "deployment_status" ? t.gov.deployment : t.gov.monitoring}</dt>
                    <dd className="mt-0.5">{manage ? (
                      <Select aria-label={f} value={u[f]} className="h-8 text-[12.5px]" onChange={(e) => patchUc.mutate({ id: u.id, body: { [f]: e.target.value } })}>
                        {(f === "approval_status" ? ["PENDING", "APPROVED", "REJECTED", "RETIRED"] : f === "deployment_status" ? ["NOT_DEPLOYED", "STAGING", "PRODUCTION"] : ["MONITORED", "DEGRADED", "NOT_MONITORED"])
                          .map((o) => <option key={o} value={o}>{label("approval", o)}</option>)}
                      </Select>) : <Badge tone={TONE[u[f]]}>{label("approval", u[f])}</Badge>}</dd></div>
                ))}
              </dl>
              {u.control_mappings.length > 0 && (
                <div className="mt-4">
                  <p className="mb-2 text-[12px] text-muted">{t.gov.mappings}</p>
                  <ul className="flex flex-wrap gap-2">
                    {u.control_mappings.map((m, i) => (
                      <li key={i} className="flex items-center gap-2 rounded-md border border-line px-2.5 py-1 text-[12.5px]">
                        <span>{fw[m.framework] ?? m.framework}</span><span className="ltr text-muted">{m.control_ref}</span><Badge tone={TONE[m.status]}>{label("approval", m.status)}</Badge>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </article>
          ))}
        </TabPanel>
        <TabPanel value="models">
          <div className="rounded-xl border border-line bg-surface">
            {!models.data ? <SkeletonRows className="p-5" /> : (
              <Table>
                <thead><tr><Th>{t.gov.models}</Th><Th>{t.gov.provider}</Th><Th>{t.gov.hosting}</Th><Th>{t.gov.approval}</Th><Th>{t.gov.deployment}</Th><Th>{t.gov.capabilities}</Th></tr></thead>
                <tbody>{models.data.map((m) => (
                  <Tr key={m.id}>
                    <Td><p className="font-medium">{m.name} {m.is_active && <Badge tone="primary">{pick("نشط", "Active")}</Badge>}</p><p className="ltr text-start text-[12px] text-muted">{m.model_id} · {m.purpose}</p>
                      {m.notes && <p dir="ltr" className="mt-1 max-w-md text-start text-[12px] text-muted">{m.notes}</p>}</Td>
                    <Td className="ltr text-[12.5px]">{m.provider}</Td>
                    <Td className="text-[12.5px]">{m.hosting === "self_hosted" ? pick("استضافة ذاتية", "Self-hosted") : pick("مستضاف", "Hosted")}</Td>
                    <Td><Badge tone={TONE[m.approval_status]}>{label("approval", m.approval_status)}</Badge></Td>
                    <Td><Badge tone={TONE[m.deployment_status]}>{label("approval", m.deployment_status)}</Badge></Td>
                    <Td className="text-[12px]">{m.capabilities && Object.keys(m.capabilities).length ? (
                      <div className="flex flex-wrap gap-1">{Object.entries(m.capabilities).filter(([, v]) => typeof v === "boolean").map(([k, v]) => (
                        <span key={k} className={`ltr rounded px-1.5 ${v ? "bg-success-soft text-success" : "bg-surface-2 text-faint line-through"}`}>{k}</span>))}</div>
                    ) : <span className="text-faint">{t.gov.notProbed}</span>}</Td>
                  </Tr>))}
                </tbody>
              </Table>
            )}
          </div>
        </TabPanel>
        <TabPanel value="evaluations" className="flex flex-col gap-4">
          {!evals.data ? <SkeletonRows /> : evals.data.length === 0 ? <EmptyState icon={FlaskConical} title={t.gov.noEvals} /> : evals.data.map((e) => (
            <Panel key={e.id} title={<span className="ltr">{e.model_name}</span>} description={`${fmtDate(e.created_at, true)} — ${e.dataset}`}
              actions={e.is_mock && <Badge tone="warning">{t.demo.mock}</Badge>}>
              {e.is_mock && <Notice tone="warning" className="mb-4">{t.gov.mockEval}</Notice>}
              <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4 lg:grid-cols-7">
                {([["precision_at_k", t.gov.precision], ["recall_at_k", t.gov.recall], ["mrr", t.gov.mrr], ["context_relevance", t.gov.contextRel],
                  ["groundedness", t.gov.groundedness], ["answer_relevance", t.gov.answerRel], ["citation_correctness", t.gov.citation]] as const).map(([k, l]) => (
                  <div key={k}><dt className="text-[12px] text-muted">{l}</dt><dd className="text-[19px] font-semibold num">{e.metrics[k] != null ? fmtNum(e.metrics[k], { maximumFractionDigits: 2 }) : "—"}</dd></div>
                ))}
              </dl>
              {e.metrics.by_language && (
                <p className="mt-4 border-t border-line pt-3 text-[12.5px] text-muted">
                  {Object.entries(e.metrics.by_language as Record<string, Record<string, number>>).map(([lng, m]) => (
                    <span key={lng} className="me-6">{lng === "ar" ? "العربية" : "English"}: {t.gov.recall} <span className="num">{fmtNum(m.recall_at_k, { maximumFractionDigits: 2 })}</span>, MRR <span className="num">{fmtNum(m.mrr, { maximumFractionDigits: 2 })}</span></span>
                  ))}
                  <span>k = <span className="num">{e.metrics.k}</span>, n = <span className="num">{e.sample_count}</span></span>
                </p>
              )}
            </Panel>
          ))}
        </TabPanel>
        <TabPanel value="controls">
          <Notice tone="warning" className="mb-4">{t.gov.controlsNotice}</Notice>
          {!controls.data ? <SkeletonRows /> : (
            <div className="grid gap-4 lg:grid-cols-2">
              {Object.entries(controls.data.items.reduce<Record<string, Control[]>>((acc, c) => { (acc[c.framework] ??= []).push(c); return acc; }, {})).map(([f, items]) => (
                <Panel key={f} title={fw[f] ?? f} bodyClass="p-0">
                  <ul className="divide-y divide-line">{items.map((c) => (
                    <li key={c.id} className="flex gap-4 px-5 py-3">
                      <span className="ltr w-24 shrink-0 text-[12.5px] font-medium text-ink-2">{c.reference}</span>
                      <div><p className="text-[13.5px] font-medium">{pick(c.title_ar, c.title_en)}</p><p className="text-[12.5px] text-muted">{pick(c.description_ar, c.description_en)}</p></div>
                    </li>))}
                  </ul>
                </Panel>
              ))}
            </div>
          )}
        </TabPanel>
      </Tabs>
    </div>
  );
}
