"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { useEffect, useState } from "react";
import { HBars, TrendLine } from "@/components/charts/charts";
import { Badge } from "@/components/ui/badge";
import { Drawer } from "@/components/ui/dialog";
import { Input, Segmented, Select } from "@/components/ui/field";
import { EmptyState, ErrorState, Skeleton, SkeletonRows } from "@/components/ui/feedback";
import { DescList, PageHeader, Panel, TabPanel, Tabs } from "@/components/ui/layout";
import { Pagination, Table, Td, Th, Tr } from "@/components/ui/table";
import { api } from "@/lib/api";
import { labels } from "@/lib/dictionaries";
import { useI18n } from "@/lib/i18n";

type Row = { id: string; created_at: string; category: string; action: string; outcome: string; actor_type: string; actor_name_ar: string | null; actor_name_en: string | null;
  resource_type: string; resource_id: string; ip_address: string | null; details: Record<string, unknown>; request_id: string };
type Metrics = {
  api: { requests: number; p50_ms: number | null; p95_ms: number | null; errors_5xx: number; errors_4xx: number; series: { t: string; requests: number; p95: number }[]; slowest_routes: { route: string; p95_ms: number; count: number }[] };
  models: { key: string; count: number; avg_latency_ms: number; p95_latency_ms: number; tokens: number; cost_usd: number; failures: number; is_mock: boolean }[];
  agents: { runs: number; failed: number; avg_duration_ms: number | null; avg_tool_calls: number | null };
  tools: { tool: string; calls: number; failures: number; p95_ms: number | null }[];
  retrieval: { queries: number; p50_ms: number | null; p95_ms: number | null };
  citations: { total: number; verified: number; accuracy: number | null };
  human_corrections: { reviewed_findings: number; edited: number; dismissed: number; correction_rate: number | null };
};

export default function Audit() {
  const { t } = useI18n();
  const [tab, setTab] = useState("log");
  return (
    <div>
      <PageHeader title={t.audit.title} subtitle={t.audit.subtitle} />
      <Tabs value={tab} onValueChange={setTab} items={[{ value: "log", label: t.audit.log }, { value: "monitoring", label: t.audit.monitoring }]}>
        <TabPanel value="log"><AuditLog /></TabPanel>
        <TabPanel value="monitoring"><Monitoring /></TabPanel>
      </Tabs>
    </div>
  );
}

function AuditLog() {
  const { t, label, pick, fmtDate } = useI18n();
  const [category, setCategory] = useState("");
  const [outcome, setOutcome] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [sel, setSel] = useState<Row | null>(null);
  useEffect(() => setPage(1), [category, outcome, q]);
  const res = useQuery({ queryKey: ["audit", category, outcome, q, page], placeholderData: (p) => p,
    queryFn: () => api<{ items: Row[]; total: number }>("/audit", { query: { category, outcome, q, page, page_size: 25 } }) });
  return (
    <div className="rounded-xl border border-line bg-surface">
      <div className="flex flex-wrap gap-3 border-b border-line px-5 py-3.5">
        <Input className="max-w-xs" placeholder={t.audit.action} value={q} onChange={(e) => setQ(e.target.value)} aria-label={t.audit.action} dir="ltr" />
        <Select aria-label={t.audit.category} value={category} onChange={(e) => setCategory(e.target.value)} className="min-w-44">
          <option value="">{t.audit.category}: {t.common.all}</option>
          {Object.keys(labels.auditCat).map((c) => <option key={c} value={c}>{label("auditCat", c)}</option>)}
        </Select>
        <Select aria-label={t.audit.outcome} value={outcome} onChange={(e) => setOutcome(e.target.value)} className="min-w-36">
          <option value="">{t.audit.outcome}: {t.common.all}</option>
          {Object.keys(labels.outcome).map((c) => <option key={c} value={c}>{label("outcome", c)}</option>)}
        </Select>
      </div>
      {res.isError ? <ErrorState error={res.error} /> : !res.data ? <SkeletonRows className="p-5" rows={10} /> : res.data.items.length === 0 ? <EmptyState icon={Activity} title={t.common.emptyTitle} /> : (
        <>
          <Table>
            <thead><tr><Th>{t.common.date}</Th><Th>{t.audit.category}</Th><Th>{t.audit.action}</Th><Th>{t.audit.actor}</Th><Th>{t.audit.resource}</Th><Th>{t.audit.outcome}</Th></tr></thead>
            <tbody>{res.data.items.map((r) => (
              <Tr key={r.id} onClick={() => setSel(r)}>
                <Td className="whitespace-nowrap text-[12.5px] text-ink-2">{fmtDate(r.created_at, true)}</Td>
                <Td className="text-[12.5px]">{label("auditCat", r.category)}</Td>
                <Td><code className="ltr text-[12.5px]">{r.action}</code></Td>
                <Td className="text-[12.5px]">{r.actor_type === "USER" ? pick(r.actor_name_ar, r.actor_name_en) : <Badge tone="accent">{r.actor_type}</Badge>}</Td>
                <Td className="ltr max-w-[200px] truncate text-start text-[12px] text-muted">{r.resource_type}{r.resource_id ? `/${r.resource_id.slice(0, 12)}` : ""}</Td>
                <Td><Badge tone={r.outcome === "SUCCESS" ? "success" : r.outcome === "DENIED" ? "danger" : "warning"}>{label("outcome", r.outcome)}</Badge></Td>
              </Tr>))}
            </tbody>
          </Table>
          <Pagination page={page} pageSize={25} total={res.data.total} onPage={setPage} />
        </>
      )}
      <Drawer open={!!sel} onOpenChange={(o) => !o && setSel(null)} title={sel?.action ?? ""} subtitle={sel && fmtDate(sel.created_at, true)}>
        {sel && (
          <>
            <DescList items={[
              { label: t.audit.category, value: label("auditCat", sel.category) }, { label: t.audit.outcome, value: label("outcome", sel.outcome) },
              { label: t.audit.actor, value: `${sel.actor_type} ${pick(sel.actor_name_ar, sel.actor_name_en) ?? ""}` },
              { label: t.audit.resource, value: <span className="ltr break-all">{sel.resource_type} {sel.resource_id}</span> },
              { label: t.audit.ip, value: <span className="ltr">{sel.ip_address}</span> }, { label: t.audit.requestId, value: <span className="ltr break-all">{sel.request_id}</span> },
            ]} />
            <pre dir="ltr" className="mt-5 overflow-auto rounded-lg border border-line bg-canvas p-4 text-[12px] leading-relaxed">{JSON.stringify(sel.details, null, 2)}</pre>
          </>
        )}
      </Drawer>
    </div>
  );
}

function Monitoring() {
  const { t, fmtNum, fmtDate } = useI18n();
  const [hours, setHours] = useState("168");
  const q = useQuery({ queryKey: ["observability", hours], queryFn: () => api<Metrics>("/observability/metrics", { query: { hours } }) });
  if (q.isError) return <ErrorState error={q.error} />;
  const m = q.data;
  const stat = (l: string, v: string) => <div><dt className="text-[12px] text-muted">{l}</dt><dd className="mt-0.5 text-[19px] font-semibold num">{v}</dd></div>;
  const ms = (v: number | null | undefined) => (v == null ? "—" : `${fmtNum(v)} ${t.common.ms}`);
  const pct = (v: number | null | undefined) => (v == null ? "—" : fmtNum(v, { style: "percent", maximumFractionDigits: 1 }));
  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-end"><Segmented value={hours} onChange={setHours} options={[{ value: "24", label: "24h" }, { value: "168", label: "7d" }, { value: "720", label: "30d" }]} /></div>
      {!m ? <Skeleton className="h-96" /> : <>
        <Panel title={t.audit.apiLatency}>
          <dl className="mb-5 grid grid-cols-2 gap-4 sm:grid-cols-5">
            {stat(t.audit.requests, fmtNum(m.api.requests))}{stat(t.audit.p50, ms(m.api.p50_ms))}{stat(t.audit.p95, ms(m.api.p95_ms))}
            {stat("5xx", fmtNum(m.api.errors_5xx))}{stat("4xx", fmtNum(m.api.errors_4xx))}
          </dl>
          <TrendLine data={m.api.series.map((s) => ({ ...s, label: fmtDate(s.t, true) }))} x="label" y="p95" unit={t.common.ms} height={200} />
        </Panel>
        <div className="grid gap-6 xl:grid-cols-2">
          <Panel title={t.audit.modelUsage} bodyClass="p-0">
            <Table><thead><tr><Th>{t.gov.provider}</Th><Th className="text-end">{t.audit.calls}</Th><Th className="text-end">{t.audit.p95}</Th><Th className="text-end">{t.dashboard.tokens}</Th><Th className="text-end">{t.audit.cost}</Th><Th className="text-end">{t.audit.failures}</Th></tr></thead>
              <tbody>{m.models.map((x) => (
                <Tr key={x.key}><Td className="ltr text-start text-[12.5px]">{x.key}{x.is_mock ? " (mock)" : ""}</Td><Td className="text-end num">{fmtNum(x.count)}</Td>
                  <Td className="text-end num">{ms(x.p95_latency_ms)}</Td><Td className="text-end num">{fmtNum(x.tokens)}</Td><Td className="text-end num">${fmtNum(x.cost_usd, { maximumFractionDigits: 4 })}</Td>
                  <Td className="text-end num">{fmtNum(x.failures)}</Td></Tr>))}</tbody></Table>
          </Panel>
          <Panel title={t.audit.toolHealth} bodyClass="p-0">
            <Table><thead><tr><Th>{t.mcp.tool}</Th><Th className="text-end">{t.audit.calls}</Th><Th className="text-end">{t.audit.failures}</Th><Th className="text-end">{t.audit.p95}</Th></tr></thead>
              <tbody>{m.tools.map((x) => (
                <Tr key={x.tool}><Td><code className="ltr text-[12.5px]">{x.tool}</code></Td><Td className="text-end num">{fmtNum(x.calls)}</Td>
                  <Td className={`text-end num ${x.failures ? "text-danger" : ""}`}>{fmtNum(x.failures)}</Td><Td className="text-end num">{ms(x.p95_ms)}</Td></Tr>))}</tbody></Table>
          </Panel>
        </div>
        <Panel title={t.dashboard.aiPerformance}>
          <dl className="grid grid-cols-2 gap-5 sm:grid-cols-3 lg:grid-cols-6">
            {stat(t.dashboard.runs, fmtNum(m.agents.runs))}{stat(t.audit.agentDuration, ms(m.agents.avg_duration_ms))}
            {stat(t.audit.retrieval, ms(m.retrieval.p95_ms))}{stat(t.audit.citationAccuracy, pct(m.citations.accuracy))}
            {stat(t.audit.corrections, pct(m.human_corrections.correction_rate))}{stat(t.audit.failures, fmtNum(m.agents.failed))}
          </dl>
        </Panel>
        <Panel title={t.audit.slowRoutes}>
          <HBars data={m.api.slowest_routes.map((r) => ({ label: r.route.replace("/api/v1", ""), value: Math.round(r.p95_ms ?? 0), color: "#6479E8" }))} />
        </Panel>
      </>}
    </div>
  );
}
