"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Donut, GroupedBars, HBars, PercentBars, TrendLine } from "@/components/charts/charts";
import { MockTag, Severity } from "@/components/domain/badges";
import { Select, Segmented } from "@/components/ui/field";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { PageHeader, Panel } from "@/components/ui/layout";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { labels } from "@/lib/dictionaries";
import { useI18n } from "@/lib/i18n";

type Summary = {
  kpis: Record<string, number | null>; by_status: Record<string, number>; by_category: Record<string, number>;
  trend: { week: string; count: number }[]; risk_distribution: Record<string, number>;
  workload: { user_id: string; name_ar: string; name_en: string; open: number; pending_review: number }[];
  ai: { invocations: number; avg_latency_ms: number | null; tokens: number; cost_usd: number; runs: number; citation_verification_rate: number | null; is_mock: boolean };
  recent_findings: { id: string; severity: string; category: string; title_ar: string; title_en: string; application_id: string; reference: string; company_name_ar: string; company_name_en: string }[];
  insights: { avg_readiness: number | null; readiness_by_category: Record<string, number>; top_gaps: { code: string; title_ar: string; title_en: string; count: number }[];
    doc_coverage: Record<string, number>; monthly: { month: string; submitted: number; approved: number; info: number }[];
    decisions: Record<string, number>; cities: Record<string, number>; assessed: number };
  activity: { id: string; action: string; category: string; created_at: string; actor_type: string; actor_name_ar: string | null; actor_name_en: string | null }[];
};

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "#B7C2D1", SUBMITTED: "#2457D6", DOCUMENT_PROCESSING: "#8C9CF0", AI_ANALYSIS: "#6479E8", PENDING_HUMAN_REVIEW: "#D99024",
  ADDITIONAL_INFORMATION_REQUIRED: "#D94B52", APPROVED_FOR_NEXT_REVIEW_STAGE: "#15966A", CLOSED: "#68778B",
};
const CAT_COLORS: Record<string, string> = { BNPL: "#2457D6", DIGITAL_PAYMENTS: "#6479E8", DIGITAL_WALLET: "#15966A", OPEN_BANKING: "#D99024", LENDING: "#C8414A" };
const DECISION_COLORS: Record<string, string> = { APPROVE_FOR_NEXT_STAGE: "#15966A", REQUEST_INFORMATION: "#D99024", COMMENT: "#6479E8", RETURN: "#68778B", REJECT: "#D94B52" };
const RISK_COLORS: Record<string, string> = { CRITICAL: "#B4232A", HIGH: "#D94B52", MEDIUM: "#D99024", LOW: "#15966A", UNDETERMINED: "#B7C2D1" };

function Kpi({ label, value, hint, href }: { label: string; value: React.ReactNode; hint?: string; href?: string }) {
  const body = (
    <div className="flex h-full flex-col justify-between gap-3 px-5 py-4">
      <p className="text-[12.5px] leading-snug text-muted">{label}</p>
      <div>
        <p className="text-[26px] font-semibold leading-none tracking-[-0.02em] text-ink num">{value}</p>
        {hint && <p className="mt-1.5 text-[12px] text-muted">{hint}</p>}
      </div>
    </div>
  );
  return href ? <Link href={href} className="block hover:bg-canvas">{body}</Link> : body;
}

function actionLabel(action: string, locale: "ar" | "en") {
  const ar: Record<string, string> = {
    status_changed: "غيّر حالة طلب", application_created: "أنشأ طلباً", application_document_uploaded: "رفع وثيقة", assessment_draft_created: "أعدّ مسودة تقييم",
    assessment_run_started: "بدأ تقييماً ذكياً", assessment_run_finished: "أنهى تقييماً ذكياً", submitted_for_human_review: "أحال مسودة للمراجعة",
    review_approve_for_next_stage: "أحال تقييماً للمرحلة التالية", review_request_information: "طلب استكمال بيانات", review_comment: "أضاف ملاحظة مراجعة",
    comment_added: "أضاف ملاحظة", assessment_edited: "عدّل تقييماً", regulatory_document_indexed: "فهرس وثيقة تنظيمية", report_exported: "صدّر تقريراً",
    extracted_profile_stored: "حفظ البيانات المستخرجة", analyst_assigned: "أسند طلباً", information_requested: "طلب معلومات إضافية",
  };
  return locale === "ar" ? (ar[action] ?? action) : action.replaceAll("_", " ");
}

export default function Dashboard() {
  const { t, pick, fmtNum, label, locale, fmtRelative, fmtDate } = useI18n();
  const { me } = useAuth();
  const [days, setDays] = useState("90");
  const [category, setCategory] = useState("");
  const q = useQuery({ queryKey: ["dashboard", days, category], queryFn: () => api<Summary>("/dashboard/summary", { query: { days, category } }) });
  const d = q.data;
  const k = d?.kpis;

  return (
    <div>
      <PageHeader
        title={me ? `${t.dashboard.greeting}، ${pick(me.full_name_ar.split(" ")[0], me.full_name_en.split(" ")[0])}` : t.dashboard.title}
        subtitle={t.dashboard.subtitle}
        meta={<MockTag show={!!d?.ai.is_mock} />}
        actions={<>
          <Select aria-label={t.apps.category} value={category} onChange={(e) => setCategory(e.target.value)} className="min-w-44">
            <option value="">{t.common.all}</option>
            {Object.keys(labels.category).map((c) => <option key={c} value={c}>{label("category", c)}</option>)}
          </Select>
          <Segmented ariaLabel={t.dashboard.period} value={days} onChange={setDays}
            options={["30", "90", "365"].map((v) => ({ value: v, label: `${fmtNum(Number(v))} ${t.dashboard.days}` }))} />
        </>}
      />

      {q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : (
        <>
          <section aria-label={t.dashboard.title} className="grid grid-cols-2 overflow-hidden rounded-xl border border-line bg-surface md:grid-cols-3 xl:grid-cols-6 [&>*]:border-line [&>*]:border-b xl:[&>*]:border-b-0 [&>*:not(:last-child)]:border-e">
            {!k ? Array.from({ length: 6 }).map((_, i) => <div key={i} className="p-5"><Skeleton className="mb-4 w-2/3" /><Skeleton className="h-7 w-1/3" /></div>) : <>
              <Kpi label={t.dashboard.totalApps} value={fmtNum(k.total_applications)} href="/applications" />
              <Kpi label={t.dashboard.underReview} value={fmtNum(k.under_review)} href="/applications?status=PENDING_HUMAN_REVIEW" />
              <Kpi label={t.dashboard.completed} value={fmtNum(k.completed_assessments)} href="/assessments" />
              <Kpi label={t.dashboard.needsInfo} value={fmtNum(k.requires_information)} href="/applications?status=ADDITIONAL_INFORMATION_REQUIRED" />
              <Kpi label={t.dashboard.riskIndicators} value={fmtNum(k.risk_indicators)} href="/reviews" />
              <Kpi label={t.dashboard.regDocs} value={fmtNum(k.regulatory_documents)} href="/knowledge" />
            </>}
          </section>

          <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
            <Panel title={t.dashboard.trend} description={`${fmtNum(Number(days))} ${t.dashboard.days}`}>
              {!d ? <Skeleton className="h-[220px]" /> : d.trend.length ? (
                <TrendLine data={d.trend.map((r) => ({ ...r, label: fmtDate(r.week) }))} x="label" y="count" />
              ) : <EmptyState title={t.common.emptyTitle} />}
            </Panel>
            <Panel title={t.dashboard.byStatus}>
              {!d ? <Skeleton className="h-40" /> : (
                <Donut centerLabel={pick("طلب", "applications")}
                  parts={Object.keys(labels.status).filter((s) => d.by_status[s]).map((s) => ({ label: label("status", s), value: d.by_status[s] ?? 0, color: STATUS_COLORS[s] }))} />
              )}
            </Panel>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
            <Panel title={pick("التدفق الشهري للطلبات", "Monthly application flow")} description={pick("آخر 6 أشهر", "Last 6 months")} className="xl:col-span-1 lg:col-span-2">
              {!d ? <Skeleton className="h-56" /> : (
                <GroupedBars x="label" data={d.insights.monthly.map((m) => ({ ...m, label: new Date(m.month + "-01").toLocaleDateString(locale === "ar" ? "ar-SA-u-nu-latn-ca-gregory" : "en-US", { month: "short" }) }))}
                  series={[{ key: "submitted", label: pick("مقدَّمة", "Submitted"), color: "#2457D6" }, { key: "approved", label: pick("محالة للمرحلة التالية", "Advanced"), color: "#15966A" },
                    { key: "info", label: pick("بانتظار استكمال", "Awaiting info"), color: "#D99024" }]} />
              )}
            </Panel>
            <Panel title={t.dashboard.byCategory}>
              {!d ? <Skeleton className="h-40" /> : (
                <Donut centerLabel={pick("طلب", "applications")}
                  parts={Object.keys(labels.category).map((c) => ({ label: label("category", c), value: d.by_category[c] ?? 0, color: CAT_COLORS[c] }))} />
              )}
            </Panel>
            <Panel title={t.dashboard.riskDist} description={pick("حسب آخر تقييم لكل طلب", "Latest assessment per application")}>
              {!d ? <Skeleton className="h-40" /> : (
                <Donut centerLabel={pick("تقييم", "assessed")}
                  parts={["HIGH", "MEDIUM", "LOW"].map((r) => ({ label: label("severity", r), value: d.risk_distribution[r] ?? 0, color: RISK_COLORS[r] }))} />
              )}
            </Panel>
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
            <Panel title={pick("متوسط الجاهزية حسب النشاط", "Average readiness by activity")}
              actions={d?.insights.avg_readiness != null && <span className="rounded-full bg-primary-soft px-2.5 py-0.5 text-[12.5px] font-semibold text-primary num">{pick("الإجمالي", "Overall")} {d.insights.avg_readiness}%</span>}>
              {!d ? <Skeleton className="h-40" /> : (
                <PercentBars data={Object.entries(d.insights.readiness_by_category).sort((a, b) => b[1] - a[1]).map(([c, v]) => ({ label: label("category", c), value: v }))} />
              )}
            </Panel>
            <Panel title={pick("أكثر الفجوات تكراراً", "Most common gaps")} description={pick("عدد الطلبات التي ظهرت فيها الفجوة", "Applications where the gap appears")}>
              {!d ? <Skeleton className="h-40" /> : d.insights.top_gaps.length === 0 ? <EmptyState title={t.common.emptyTitle} /> : (
                <HBars data={d.insights.top_gaps.map((g) => ({ label: pick(g.title_ar, g.title_en), value: g.count, color: "#D94B52" }))} />
              )}
            </Panel>
            <Panel title={pick("اكتمال الوثائق المقدَّمة", "Document coverage")} description={pick("نسبة الطلبات المقدَّمة التي أرفقت كل وثيقة", "Share of submitted applications with each document")}>
              {!d ? <Skeleton className="h-40" /> : (
                <PercentBars data={Object.entries(d.insights.doc_coverage).filter(([k]) => k !== "OTHER").sort((a, b) => b[1] - a[1]).slice(0, 7).map(([k, v]) => ({ label: label("docType", k), value: v }))} />
              )}
            </Panel>
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
            <Panel title={t.dashboard.recentFindings} bodyClass="p-0" actions={<Link href="/reviews" className="text-[13px] font-medium text-primary hover:underline">{t.nav.reviews}</Link>}>
              {!d ? <div className="p-5"><Skeleton className="h-40" /></div> : d.recent_findings.length === 0 ? <EmptyState title={t.dashboard.noFindings} /> : (
                <ul className="divide-y divide-line">
                  {d.recent_findings.map((f) => (
                    <li key={f.id}>
                      <Link href={`/applications/${f.application_id}`} className="flex items-start gap-4 px-5 py-3.5 hover:bg-canvas">
                        <div className="w-24 shrink-0 pt-0.5"><Severity value={f.severity} /></div>
                        <div className="min-w-0 flex-1">
                          <p className="text-[13.5px] font-medium leading-snug">{pick(f.title_ar, f.title_en)}</p>
                          <p className="mt-0.5 text-[12.5px] text-muted">{pick(f.company_name_ar, f.company_name_en)} <span className="ltr">{f.reference}</span></p>
                        </div>
                        <span className="hidden text-[12px] text-muted sm:block">{label("findingCat", f.category)}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            <Panel title={t.dashboard.aiPerformance} actions={<MockTag show={!!d?.ai.is_mock} />}>
              {!d ? <Skeleton className="h-40" /> : (
                <dl className="grid grid-cols-2 gap-x-6 gap-y-5">
                  {[
                    [t.dashboard.avgAssessment, k?.avg_assessment_seconds != null ? `${fmtNum(k.avg_assessment_seconds, { maximumFractionDigits: 1 })} ${t.common.sec}` : "—"],
                    [t.dashboard.avgFirstReview, k?.avg_hours_to_first_review != null ? `${fmtNum(k.avg_hours_to_first_review)} ${t.dashboard.hours}` : "—"],
                    [t.dashboard.runs, fmtNum(d.ai.runs)], [t.dashboard.invocations, fmtNum(d.ai.invocations)],
                    [t.dashboard.latency, d.ai.avg_latency_ms != null ? `${fmtNum(d.ai.avg_latency_ms)} ${t.common.ms}` : "—"],
                    [t.dashboard.citationRate, d.ai.citation_verification_rate != null ? fmtNum(d.ai.citation_verification_rate, { style: "percent" }) : "—"],
                    [t.dashboard.tokens, fmtNum(d.ai.tokens)],
                    [t.dashboard.successRate, k?.ai_success_rate != null ? fmtNum(k.ai_success_rate, { style: "percent", maximumFractionDigits: 1 }) : "—"],
                  ].map(([l, v]) => (
                    <div key={String(l)}><dt className="text-[12px] text-muted">{l}</dt><dd className="mt-0.5 text-[17px] font-semibold num">{v}</dd></div>
                  ))}
                </dl>
              )}
            </Panel>
          </div>

          <div className="mt-6 grid gap-6 xl:grid-cols-3">
            <Panel title={t.dashboard.workload} className="xl:col-span-1">
              {!d ? <Skeleton className="h-32" /> : (
                <HBars data={d.workload.map((w) => ({ label: pick(w.name_ar, w.name_en), value: w.open }))} />
              )}
            </Panel>
            <Panel title={pick("قرارات المراجعة البشرية", "Human review decisions")}>
              {!d ? <Skeleton className="h-32" /> : (
                <Donut size={140} centerLabel={pick("قرار", "decisions")}
                  parts={Object.entries(d.insights.decisions).map(([k, v]) => ({ label: label("decision", k), value: v, color: DECISION_COLORS[k] ?? "#98A4B5" }))} />
              )}
              {d && Object.keys(d.insights.cities).length > 0 && (
                <div className="mt-5 border-t border-line pt-4">
                  <p className="mb-3 text-[12.5px] text-muted">{pick("الطلبات حسب المدينة", "Applications by city")}</p>
                  <HBars data={Object.entries(d.insights.cities).map(([c, v]) => ({ label: c, value: v, color: "#6479E8" }))} />
                </div>
              )}
            </Panel>
            <Panel title={t.dashboard.activity} bodyClass="px-5 py-3">
              {!d ? <Skeleton className="h-32" /> : (
                <ol className="relative flex flex-col">
                  {d.activity.slice(0, 7).map((a) => (
                    <li key={a.id} className="relative flex gap-3 pb-3 ps-4 before:absolute before:start-[3px] before:top-2 before:h-full before:w-px before:bg-line last:before:hidden">
                      <span className="absolute start-0 top-[7px] size-[7px] rounded-full bg-primary/70" aria-hidden />
                      <div className="min-w-0 text-[13px]">
                        <p><span className="font-medium">{a.actor_type === "AGENT" ? pick("وكيل ذكي", "AI agent") : pick(a.actor_name_ar, a.actor_name_en) ?? pick("النظام", "System")}</span>{" "}
                          <span className="text-ink-2">{actionLabel(a.action, locale)}</span></p>
                        <p className="text-[12px] text-muted">{fmtRelative(a.created_at)}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </Panel>
          </div>
        </>
      )}
    </div>
  );
}
