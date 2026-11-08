"use client";

import * as DM from "@radix-ui/react-dropdown-menu";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, FileText, Pencil, Send, Sparkles, Upload, UserPlus } from "lucide-react";
import Link from "next/link";
import { use, useRef, useState } from "react";
import { toast } from "sonner";
import { ApplicationForm } from "@/components/domain/application-form";
import { OriginTag, RiskBadge, StatusBadge, SyntheticTag } from "@/components/domain/badges";
import { RunProgress } from "@/components/domain/run-progress";
import { Button } from "@/components/ui/button";
import { ConfirmDialog, Dialog, Drawer } from "@/components/ui/dialog";
import { Field, Select, Textarea } from "@/components/ui/field";
import { EmptyState, ErrorState, Notice, SkeletonRows } from "@/components/ui/feedback";
import { DescList, PageHeader, Panel, TabPanel, Tabs } from "@/components/ui/layout";
import { api, errorText } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { labels } from "@/lib/dictionaries";
import { useI18n } from "@/lib/i18n";
import type { AppDocument, Application, Draft, User } from "@/lib/types";
import { bytes } from "@/lib/utils";

type Event = { id: string; event_type: string; from_status: string | null; to_status: string | null; created_at: string; actor_name_ar: string | null; actor_name_en: string | null; details: Record<string, unknown> };
type Comment = { id: string; body: string; kind: string; created_at: string; author_name_ar: string; author_name_en: string };

export default function ApplicationDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t, pick, label, fmtNum, fmtDate, locale } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState("overview");
  const [editing, setEditing] = useState(false);
  const [infoOpen, setInfoOpen] = useState(false);
  const [closeOpen, setCloseOpen] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [infoText, setInfoText] = useState("");

  const appQ = useQuery({ queryKey: ["application", id], queryFn: () => api<Application>(`/applications/${id}`) });
  const docsQ = useQuery({ queryKey: ["documents", id], queryFn: () => api<AppDocument[]>(`/applications/${id}/documents`) });
  const users = useQuery({ queryKey: ["users"], queryFn: () => api<User[]>("/users"), enabled: can("applications:assign") });
  const a = appQ.data;
  const refresh = () => { ["application", "events", "comments", "documents", "app-assessments"].forEach((k) => qc.invalidateQueries({ queryKey: [k, id] })); qc.invalidateQueries({ queryKey: ["applications"] }); };

  const transition = useMutation({
    mutationFn: (to: string) => api(`/applications/${id}/transition`, { body: { to_status: to } }),
    onSuccess: (_, to) => { toast.success(to === "SUBMITTED" ? t.apps.submittedToast : t.apps.savedToast); refresh(); },
    onError: (e) => toast.error(errorText(e, locale)),
  });
  const run = useMutation({
    mutationFn: () => api<{ run_id: string }>("/assessments/run", { body: { application_id: id } }),
    onSuccess: (r) => { setRunId(r.run_id); toast.success(t.apps.runStarted); refresh(); },
    onError: (e) => toast.error(errorText(e, locale)),
  });
  const assign = useMutation({
    mutationFn: (analyst_id: string | null) => api(`/applications/${id}/assign`, { body: { analyst_id } }),
    onSuccess: () => { toast.success(t.apps.assignedToast); refresh(); }, onError: (e) => toast.error(errorText(e, locale)),
  });

  if (appQ.isError) return <ErrorState error={appQ.error} onRetry={() => appQ.refetch()} />;
  if (!a) return <SkeletonRows rows={8} />;

  const canSubmit = a.allowed_transitions.includes("SUBMITTED") && ["DRAFT", "ADDITIONAL_INFORMATION_REQUIRED"].includes(a.status);
  const canRun = can("assessments:run") && ["SUBMITTED", "DOCUMENT_PROCESSING", "PENDING_HUMAN_REVIEW", "ADDITIONAL_INFORMATION_REQUIRED"].includes(a.status);
  const editable = can("applications:write") && !["CLOSED", "APPROVED_FOR_NEXT_REVIEW_STAGE", "AI_ANALYSIS"].includes(a.status);

  return (
    <div>
      <PageHeader title={pick(a.company_name_ar, a.company_name_en)} crumbs={[{ label: t.apps.title, href: "/applications" }, { label: a.reference }]}
        meta={<><span className="ltr text-[13px] text-muted">{a.reference}</span><StatusBadge status={a.status} /><span className="text-[13px] text-ink-2">{label("category", a.service_category)}</span>{a.is_synthetic && <SyntheticTag />}</>}
        actions={<>
          {editable && <Button variant="secondary" onClick={() => setEditing(true)}><Pencil />{t.common.edit}</Button>}
          {can("applications:assign") && (
            <DM.Root dir={locale === "ar" ? "rtl" : "ltr"}>
              <DM.Trigger asChild><Button variant="secondary"><UserPlus />{t.apps.assign}<ChevronDown /></Button></DM.Trigger>
              <DM.Portal>
                <DM.Content align="end" sideOffset={6} className="z-50 min-w-56 rounded-lg border border-line bg-surface p-1 shadow-pop">
                  <DM.Label className="px-3 py-1.5 text-[12px] text-muted">{t.apps.assignTo}</DM.Label>
                  {users.data?.filter((u) => u.role_codes.some((r) => ["analyst", "supervisor"].includes(r))).map((u) => (
                    <DM.Item key={u.id} onSelect={() => assign.mutate(u.id)} className="flex items-center justify-between gap-3 rounded-md px-3 py-2 text-[13px] outline-none data-[highlighted]:bg-surface-2">
                      {pick(u.full_name_ar, u.full_name_en)}{a.assigned_analyst_id === u.id && <span className="text-primary">✓</span>}
                    </DM.Item>
                  ))}
                </DM.Content>
              </DM.Portal>
            </DM.Root>
          )}
          {canSubmit && <Button onClick={() => transition.mutate("SUBMITTED")} loading={transition.isPending}><Send />{t.apps.submit}</Button>}
          {canRun && <Button onClick={() => run.mutate()} loading={run.isPending}><Sparkles />{t.apps.runAssessment}</Button>}
        </>}
      />

      {runId && <div className="mb-6"><RunProgress runId={runId} applicationId={id} /></div>}

      <Tabs value={tab} onValueChange={setTab} items={[
        { value: "overview", label: t.apps.overview }, { value: "documents", label: t.apps.documents, count: docsQ.data?.length },
        { value: "assessments", label: t.apps.assessments }, { value: "history", label: t.apps.history }, { value: "comments", label: t.apps.comments },
      ]}>
        <TabPanel value="overview">
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
            <Panel title={t.apps.sectionCompany}>
              <DescList items={[
                { label: t.apps.companyAr, value: a.company_name_ar }, { label: t.apps.companyEn, value: <span dir="ltr">{a.company_name_en}</span> },
                { label: t.apps.cr, value: <span className="ltr">{a.commercial_registration}</span> }, { label: t.apps.city, value: a.city },
                { label: t.apps.email, value: a.contact_email && <span className="ltr">{a.contact_email}</span> },
                { label: t.apps.website, value: a.website && <span className="ltr">{a.website}</span> },
                { label: t.apps.capital, value: a.paid_up_capital_sar != null && <span className="num">{fmtNum(a.paid_up_capital_sar)}</span> },
                { label: t.apps.volume, value: a.expected_monthly_volume_sar != null && <span className="num">{fmtNum(a.expected_monthly_volume_sar)}</span> },
                { label: t.apps.hosting, value: a.data_hosting_location }, { label: t.apps.thirdParty, value: a.uses_third_party_providers ? t.common.yes : t.common.no },
                { label: t.apps.analyst, value: pick(a.assigned_analyst_name_ar, a.assigned_analyst_name_en) }, { label: t.apps.submitted, value: a.submitted_at && fmtDate(a.submitted_at, true) },
              ]} />
              <div className="mt-6 border-t border-line pt-5">
                <p className="text-[12.5px] text-muted">{t.apps.businessModel}</p>
                <p className="mt-1 text-[14px] leading-relaxed">{a.business_model || "—"}</p>
                <p className="mt-4 text-[12.5px] text-muted">{t.apps.targetCustomers}</p>
                <p className="mt-1 text-[14px] leading-relaxed">{a.target_customers || "—"}</p>
              </div>
            </Panel>
            <div className="flex flex-col gap-6">
              <Panel title={t.apps.latestRisk}><RiskBadge value={a.latest_risk} /></Panel>
              <Panel title={t.apps.extracted}>
                {Object.keys(a.extracted_profile ?? {}).length === 0 ? <p className="text-[13px] text-muted">{t.apps.noExtracted}</p> : (
                  <DescList cols={1} items={Object.entries(a.extracted_profile).map(([k, v]) => ({ label: label("profile", k) === k ? k.replaceAll("_", " ") : label("profile", k), value: <span className="num">{typeof v === "number" ? fmtNum(v) : typeof v === "boolean" ? (v ? t.common.yes : t.common.no) : String(v)}</span> }))} />
                )}
              </Panel>
              {(can("reviews:write") || editable) && (
                <Panel title={t.common.actions} bodyClass="flex flex-wrap gap-2 p-5">
                  {can("reviews:write") && !["CLOSED", "APPROVED_FOR_NEXT_REVIEW_STAGE", "ADDITIONAL_INFORMATION_REQUIRED", "DRAFT", "AI_ANALYSIS"].includes(a.status) &&
                    <Button variant="secondary" onClick={() => setInfoOpen(true)}>{t.apps.requestInfo}</Button>}
                  {a.allowed_transitions.includes("CLOSED") && <Button variant="danger-ghost" onClick={() => setCloseOpen(true)}>{t.apps.close}</Button>}
                </Panel>
              )}
            </div>
          </div>
        </TabPanel>
        <TabPanel value="documents"><DocumentsTab app={a} docs={docsQ.data} onChanged={refresh} /></TabPanel>
        <TabPanel value="assessments"><AssessmentsTab id={id} /></TabPanel>
        <TabPanel value="history"><HistoryTab id={id} /></TabPanel>
        <TabPanel value="comments"><CommentsTab id={id} /></TabPanel>
      </Tabs>

      <Drawer open={editing} onOpenChange={setEditing} title={t.common.edit} width="max-w-3xl">
        <ApplicationForm initial={a} submitLabel={t.common.save} onCancel={() => setEditing(false)} onSubmit={async (v) => {
          try { await api(`/applications/${id}`, { method: "PATCH", body: v }); toast.success(t.apps.savedToast); setEditing(false); refresh(); }
          catch (e) { toast.error(errorText(e, locale)); }
        }} />
      </Drawer>

      <Dialog open={infoOpen} onOpenChange={setInfoOpen} title={t.apps.requestInfo} description={t.apps.requestInfoHint}
        footer={<><Button variant="secondary" onClick={() => setInfoOpen(false)}>{t.common.cancel}</Button>
          <Button disabled={infoText.trim().length < 3} onClick={async () => {
            try { await api(`/applications/${id}/request-information`, { body: { body: infoText } }); toast.success(t.apps.infoRequested); setInfoOpen(false); setInfoText(""); refresh(); }
            catch (e) { toast.error(errorText(e, locale)); }
          }}>{t.apps.requestInfo}</Button></>}>
        <Textarea value={infoText} onChange={(e) => setInfoText(e.target.value)} placeholder={t.apps.requestInfoPlaceholder} rows={5} aria-label={t.apps.requestInfo} />
      </Dialog>
      <ConfirmDialog open={closeOpen} onOpenChange={setCloseOpen} title={t.apps.close} description={t.apps.closeConfirm} tone="danger"
        confirmLabel={t.apps.close} onConfirm={() => transition.mutateAsync("CLOSED")} />
    </div>
  );
}

function DocumentsTab({ app, docs, onChanged }: { app: Application; docs?: AppDocument[]; onChanged: () => void }) {
  const { t, label, fmtDate, locale, pick } = useI18n();
  const { can } = useAuth();
  const [type, setType] = useState("BUSINESS_PLAN");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<AppDocument | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const previewQ = useQuery({ queryKey: ["doc", preview?.id], queryFn: () => api<{ extracted_text: string }>(`/documents/${preview!.id}`), enabled: !!preview });
  const canUpload = can("documents:upload") && !["CLOSED", "APPROVED_FOR_NEXT_REVIEW_STAGE"].includes(app.status);

  const upload = async (f: File) => {
    const fd = new FormData();
    fd.append("file", f);
    fd.append("document_type", type);
    setBusy(true);
    try { await api(`/applications/${app.id}/documents`, { form: fd }); toast.success(t.apps.uploadedToast); onChanged(); }
    catch (e) { toast.error(errorText(e, locale)); } finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
      <Panel title={t.apps.documents} bodyClass="p-0">
        {!docs ? <SkeletonRows className="p-5" /> : docs.length === 0 ? <EmptyState icon={FileText} title={t.apps.noDocs} hint={t.apps.noDocsHint} /> : (
          <ul className="divide-y divide-line">
            {docs.map((d) => (
              <li key={d.id} className="flex items-center gap-4 px-5 py-3.5">
                <span className="grid size-9 shrink-0 place-items-center rounded-md bg-surface-2 text-muted"><FileText className="size-4" /></span>
                <div className="min-w-0 flex-1">
                  <p className="text-[13.5px] font-medium">{label("docType", d.document_type)}</p>
                  <p className="ltr truncate text-start text-[12px] text-muted">{d.filename} · {bytes(d.size_bytes)}</p>
                </div>
                <div className="hidden text-end text-[12px] text-muted sm:block">
                  <p>{fmtDate(d.created_at)}</p>
                  <p className={d.processing_status === "FAILED" ? "text-danger" : ""}>{d.processing_status === "FAILED" ? t.apps.unprocessed : `${t.apps.scan}: ${d.scan_status === "NOT_SCANNED" ? pick("غير مفعّل", "disabled") : d.scan_status}`}</p>
                </div>
                <Button variant="ghost" size="sm" onClick={() => setPreview(d)}>{t.apps.preview}</Button>
              </li>
            ))}
          </ul>
        )}
      </Panel>
      {canUpload && (
        <Panel title={t.apps.uploadDoc}>
          <div className="flex flex-col gap-4">
            <Field label={t.apps.docType} htmlFor="dtype">
              <Select id="dtype" value={type} onChange={(e) => setType(e.target.value)}>
                {Object.keys(labels.docType).map((k) => <option key={k} value={k}>{label("docType", k)}</option>)}
              </Select>
            </Field>
            <label className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-line-strong bg-canvas px-4 py-8 text-center hover:border-primary/50"
              onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) upload(f); }}>
              <Upload className="size-5 text-muted" />
              <span className="text-[13px] text-ink-2">{busy ? t.common.uploading : t.apps.chooseFile}</span>
              <input ref={fileRef} type="file" accept=".pdf,.docx,.txt" className="sr-only" disabled={busy} onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); }} />
            </label>
          </div>
        </Panel>
      )}
      <Drawer open={!!preview} onOpenChange={(o) => !o && setPreview(null)} title={preview ? label("docType", preview.document_type) : ""}
        subtitle={<span className="ltr">{preview?.filename}</span>}>
        <Notice tone="warning" className="mb-4">{pick("محتوى مقدم من الشركة ويُعامل كبيانات وليس تعليمات.", "Applicant-supplied content, treated as data — not instructions.")}</Notice>
        {previewQ.isLoading ? <SkeletonRows /> : <pre dir="auto" className="whitespace-pre-wrap font-[inherit] text-[13.5px] leading-[1.9]">{previewQ.data?.extracted_text || "—"}</pre>}
      </Drawer>
    </div>
  );
}

function AssessmentsTab({ id }: { id: string }) {
  const { t, fmtDate, label } = useI18n();
  const q = useQuery({ queryKey: ["app-assessments", id], queryFn: () => api<(Draft & { finding_count: number })[]>(`/applications/${id}/assessments`) });
  if (q.isError) return <ErrorState error={q.error} />;
  if (!q.data) return <SkeletonRows />;
  if (!q.data.length) return <EmptyState icon={Sparkles} title={t.apps.noAssessments} />;
  return (
    <div className="rounded-xl border border-line bg-surface divide-y divide-line">
      {q.data.map((d) => (
        <Link key={d.id} href={`/assessments/${d.id}`} className="flex flex-wrap items-center gap-4 px-5 py-4 hover:bg-canvas">
          <span className="text-[13.5px] font-medium">{t.assess.versionN} <span className="num">{d.version}</span></span>
          <StatusBadge status={d.status} group="draftStatus" />
          <OriginTag origin={d.authored_by} />
          <span className="text-[12.5px] text-muted">{label("severity", d.overall_risk)} · <span className="num">{d.finding_count}</span> {t.assess.findings}</span>
          <span className="ms-auto text-[12.5px] text-muted">{fmtDate(d.created_at, true)}</span>
        </Link>
      ))}
    </div>
  );
}

function HistoryTab({ id }: { id: string }) {
  const { label, pick, fmtDate, dir } = useI18n();
  const q = useQuery({ queryKey: ["events", id], queryFn: () => api<Event[]>(`/applications/${id}/events`) });
  if (!q.data) return <SkeletonRows />;
  return (
    <ol className="max-w-3xl">
      {q.data.map((e) => (
        <li key={e.id} className="relative flex gap-4 pb-5 ps-6 before:absolute before:start-[5px] before:top-3 before:h-full before:w-px before:bg-line last:before:hidden">
          <span className="absolute start-0 top-[7px] size-[11px] rounded-full border-2 border-primary bg-surface" aria-hidden />
          <div>
            <p className="text-[13.5px] font-medium">{label("event", e.event_type)}
              {e.to_status && <span className="font-normal text-ink-2"> — {label("status", e.from_status)} {dir === "rtl" ? "←" : "→"} {label("status", e.to_status)}</span>}</p>
            <p className="text-[12.5px] text-muted">{pick(e.actor_name_ar, e.actor_name_en) ?? pick("النظام", "System")} · {fmtDate(e.created_at, true)}</p>
            {typeof e.details?.reason === "string" && e.details.reason && <p className="mt-1 text-[13px] text-ink-2">{e.details.reason}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}

function CommentsTab({ id }: { id: string }) {
  const { t, pick, fmtDate, locale } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const [body, setBody] = useState("");
  const q = useQuery({ queryKey: ["comments", id], queryFn: () => api<Comment[]>(`/applications/${id}/comments`) });
  const add = useMutation({
    mutationFn: () => api(`/applications/${id}/comments`, { body: { body } }),
    onSuccess: () => { setBody(""); qc.invalidateQueries({ queryKey: ["comments", id] }); qc.invalidateQueries({ queryKey: ["events", id] }); },
    onError: (e) => toast.error(errorText(e, locale)),
  });
  return (
    <div className="max-w-3xl">
      {can("applications:write") && (
        <form className="mb-6 flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); if (body.trim()) add.mutate(); }}>
          <Textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder={t.apps.commentPlaceholder} rows={3} aria-label={t.apps.addComment} />
          <div className="flex justify-end"><Button type="submit" size="sm" loading={add.isPending} disabled={!body.trim()}>{t.apps.addComment}</Button></div>
        </form>
      )}
      {!q.data ? <SkeletonRows /> : q.data.length === 0 ? <EmptyState title={t.common.emptyTitle} /> : (
        <ul className="flex flex-col gap-3">
          {q.data.map((c) => (
            <li key={c.id} className={`rounded-lg border px-4 py-3 ${c.kind === "INFO_REQUEST" ? "border-[#f1e0bd] bg-warning-soft/50" : "border-line bg-surface"}`}>
              <p className="text-[12.5px] text-muted"><span className="font-medium text-ink-2">{pick(c.author_name_ar, c.author_name_en)}</span> · {fmtDate(c.created_at, true)}
                {c.kind === "INFO_REQUEST" && <span className="ms-2 text-warning">{t.apps.requestInfo}</span>}</p>
              <p className="mt-1 whitespace-pre-line text-[14px] leading-relaxed">{c.body}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
