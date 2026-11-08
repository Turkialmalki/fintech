"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CornerUpLeft, FileQuestion, MessageSquare, Pencil, Plus, Send, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useState } from "react";
import { toast } from "sonner";
import { ApplicationColumn, AssessmentColumn, DraftHeaderMeta } from "@/components/domain/assessment-view";
import { Button } from "@/components/ui/button";
import { ConfirmDialog, Drawer } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/field";
import { ErrorState, Notice, SkeletonRows } from "@/components/ui/feedback";
import { PageHeader, Panel } from "@/components/ui/layout";
import { api, errorText } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { Draft, Finding } from "@/lib/types";

type Decision = "APPROVE_FOR_NEXT_STAGE" | "RETURN" | "REJECT" | "REQUEST_INFORMATION" | "COMMENT";
type AuditRow = { id: string; created_at: string; action: string; actor_name_ar: string | null; actor_name_en: string | null; actor_type: string };

export default function ReviewWorkspace({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t, pick, label, fmtDate, locale } = useI18n();
  const { can } = useAuth();
  const qc = useQueryClient();
  const router = useRouter();
  const q = useQuery({ queryKey: ["draft", id], queryFn: () => api<Draft>(`/assessments/${id}`) });
  const auditQ = useQuery({ queryKey: ["draft-audit", id], queryFn: () => api<{ items: AuditRow[] }>("/audit", { query: { resource_id: id, page_size: 20 } }), enabled: can("audit:read") });
  const [decision, setDecision] = useState<Decision | null>(null);
  const [comment, setComment] = useState("");
  const [editOpen, setEditOpen] = useState(false);
  const [statusEdits, setStatusEdits] = useState<Record<string, string>>({});

  const d = q.data;
  const editable = !!d && ["DRAFT", "PENDING_REVIEW", "RETURNED"].includes(d.status) && can("reviews:write");

  const saveVersion = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Draft>(`/assessments/${id}`, { method: "PATCH", body }),
    onSuccess: (nd) => { toast.success(t.reviews.savedVersion); setStatusEdits({}); setEditOpen(false); qc.invalidateQueries({ queryKey: ["queue"] }); router.replace(`/reviews/${nd.id}`); },
    onError: (e) => toast.error(errorText(e, locale)),
  });
  const decide = async (dec: Decision, confirmed: boolean) => {
    try {
      await api(`/assessments/${id}/decision`, { body: { decision: dec, comment, confirmed } });
      toast.success(t.reviews.decided);
      setComment("");
      ["draft", "queue", "application", "draft-audit"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    } catch (e) { toast.error(errorText(e, locale)); throw e; }
  };

  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!d) return <SkeletonRows rows={10} />;

  const findingActions = (f: Finding) => !editable ? null : (
    <>
      <span className="me-auto self-center text-[12px] text-muted">{({ CONFIRMED: t.reviews.confirmed, DISMISSED: t.reviews.dismissed, EDITED: t.reviews.edited, UNREVIEWED: t.reviews.unreviewed } as Record<string, string>)[statusEdits[f.id] ?? f.analyst_status]}</span>
      <Button size="sm" variant={statusEdits[f.id] === "CONFIRMED" ? "subtle" : "secondary"} onClick={() => setStatusEdits({ ...statusEdits, [f.id]: "CONFIRMED" })}><Check />{t.reviews.confirmFinding}</Button>
      <Button size="sm" variant={statusEdits[f.id] === "DISMISSED" ? "danger" : "secondary"} onClick={() => setStatusEdits({ ...statusEdits, [f.id]: "DISMISSED" })}><X />{t.reviews.dismissFinding}</Button>
      <Select aria-label={t.reviews.severity} value={statusEdits[`${f.id}:sev`] ?? f.severity} onChange={(e) => setStatusEdits({ ...statusEdits, [`${f.id}:sev`]: e.target.value })} className="h-8 w-32 text-[12.5px]">
        {["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"].map((s) => <option key={s} value={s}>{label("severity", s)}</option>)}
      </Select>
    </>
  );
  const pending = Object.keys(statusEdits).length;
  const findingUpdates = () => {
    const ids = new Set(Object.keys(statusEdits).map((k) => k.split(":")[0]));
    return Array.from(ids).map((fid) => ({ id: fid, ...(statusEdits[fid] ? { analyst_status: statusEdits[fid] } : {}), ...(statusEdits[`${fid}:sev`] ? { severity: statusEdits[`${fid}:sev`] } : {}) }));
  };

  return (
    <div>
      <PageHeader title={t.reviews.title} crumbs={[{ label: t.reviews.queue, href: "/reviews" }, { label: pick(d.application.company_name_ar, d.application.company_name_en) }]}
        meta={<DraftHeaderMeta draft={d} />}
        actions={editable && <>
          {pending > 0 && <Button variant="subtle" loading={saveVersion.isPending} onClick={() => saveVersion.mutate({ finding_updates: findingUpdates() })}>{t.reviews.saveVersion} ({pending})</Button>}
          <Button variant="secondary" onClick={() => setEditOpen(true)}><Pencil />{t.reviews.editReport}</Button>
        </>} />
      {!editable && <Notice className="mb-6">{t.reviews.readOnly}</Notice>}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,0.8fr)]">
        <AssessmentColumn draft={d} findingActions={findingActions} />
        <aside className="flex flex-col gap-5 xl:sticky xl:top-24 xl:self-start">
          <Panel title={t.reviews.decision}>
            {can("reviews:write") ? (
              <div className="flex flex-col gap-3">
                <Field label={t.reviews.commentLabel} htmlFor="rc"><Textarea id="rc" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} /></Field>
                <div className="grid gap-2">
                  {can("reviews:approve") && <Button disabled={!editable} onClick={() => setDecision("APPROVE_FOR_NEXT_STAGE")}><Send />{t.reviews.approve}</Button>}
                  <Button variant="secondary" disabled={!editable || !comment.trim()} onClick={() => setDecision("REQUEST_INFORMATION")}><FileQuestion />{t.reviews.requestInfo}</Button>
                  <Button variant="secondary" disabled={!editable || !comment.trim()} onClick={() => decide("RETURN", false)}><CornerUpLeft />{t.reviews.return}</Button>
                  <Button variant="ghost" disabled={!comment.trim()} onClick={() => decide("COMMENT", false)}><MessageSquare />{t.reviews.comment}</Button>
                  {can("reviews:approve") && <Button variant="danger-ghost" disabled={!editable} onClick={() => setDecision("REJECT")}>{t.reviews.reject}</Button>}
                </div>
                <p className="text-[12px] leading-relaxed text-muted">{t.apps.workflowNote}</p>
              </div>
            ) : <p className="text-[13px] text-muted">{t.errors.forbidden}</p>}
          </Panel>
          <Panel title={t.reviews.previousVersions} bodyClass="p-2">
            <ul>
              {d.versions.map((v) => (
                <li key={v.id}><Link href={`/reviews/${v.id}`} aria-current={v.id === d.id}
                  className={`flex items-center justify-between rounded-md px-3 py-2 text-[13px] ${v.id === d.id ? "bg-primary-soft/60" : "hover:bg-surface-2"}`}>
                  <span>{t.assess.versionN} <span className="num">{v.version}</span> <span className="text-muted">· {label("draftStatus", v.status)}</span></span>
                  <span className="text-[12px] text-muted">{fmtDate(v.created_at)}</span>
                </Link></li>
              ))}
            </ul>
          </Panel>
          <details className="rounded-xl border border-line bg-surface">
            <summary className="cursor-pointer px-5 py-3.5 text-[14px] font-semibold">{t.assess.application}</summary>
            <div className="border-t border-line p-3"><ApplicationColumn draft={d} /></div>
          </details>
          {auditQ.data && (
            <Panel title={t.reviews.auditTrail} bodyClass="px-5 py-3">
              <ol className="flex flex-col gap-2 text-[12.5px]">
                {auditQ.data.items.map((a) => (
                  <li key={a.id} className="flex justify-between gap-3"><span className="text-ink-2">{a.action.replaceAll("_", " ")} — {a.actor_type === "AGENT" ? pick("وكيل", "agent") : pick(a.actor_name_ar, a.actor_name_en)}</span>
                    <span className="shrink-0 text-muted">{fmtDate(a.created_at, true)}</span></li>
                ))}
              </ol>
            </Panel>
          )}
        </aside>
      </div>

      <ConfirmDialog open={decision === "APPROVE_FOR_NEXT_STAGE" || decision === "REJECT" || decision === "REQUEST_INFORMATION"} onOpenChange={(o) => !o && setDecision(null)}
        title={t.reviews.confirmTitle} tone={decision === "REJECT" ? "danger" : "primary"}
        description={decision === "REJECT" ? t.reviews.rejectHint : decision === "REQUEST_INFORMATION" ? t.apps.requestInfoHint : t.reviews.approveHint}
        confirmLabel={decision ? label("decision", decision) : ""} acknowledge={t.reviews.confirmCheck}
        onConfirm={() => decide(decision!, true)}>
        {comment && <p className="mb-2 rounded-md bg-surface-2 px-3 py-2 text-[13px]">{comment}</p>}
      </ConfirmDialog>

      <EditDrawer open={editOpen} onOpenChange={setEditOpen} draft={d} busy={saveVersion.isPending}
        onSave={(body) => saveVersion.mutate({ ...body, finding_updates: findingUpdates() })} />
    </div>
  );
}

function EditDrawer({ open, onOpenChange, draft, onSave, busy }: {
  open: boolean; onOpenChange: (o: boolean) => void; draft: Draft; busy: boolean; onSave: (b: Record<string, unknown>) => void;
}) {
  const { t, label } = useI18n();
  const [summaryAr, setSummaryAr] = useState(draft.summary_ar);
  const [summaryEn, setSummaryEn] = useState(draft.summary_en);
  const [notes, setNotes] = useState(draft.analyst_notes);
  const [nf, setNf] = useState({ title_ar: "", title_en: "", severity: "MEDIUM", category: "OBSERVATION", interpretation_ar: "" });
  const [newFindings, setNewFindings] = useState<typeof nf[]>([]);
  return (
    <Drawer open={open} onOpenChange={onOpenChange} title={t.reviews.editReport} subtitle={t.reviews.saveVersion} width="max-w-3xl">
      <div className="flex flex-col gap-5">
        <Field label={`${t.assess.summary} (AR)`} htmlFor="sar"><Textarea id="sar" dir="rtl" rows={5} value={summaryAr} onChange={(e) => setSummaryAr(e.target.value)} /></Field>
        <Field label={`${t.assess.summary} (EN)`} htmlFor="sen"><Textarea id="sen" dir="ltr" rows={4} value={summaryEn} onChange={(e) => setSummaryEn(e.target.value)} /></Field>
        <Field label={t.reviews.analystNotes} htmlFor="notes"><Textarea id="notes" rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        <fieldset className="rounded-lg border border-line p-4">
          <legend className="px-1 text-[13px] font-semibold">{t.reviews.addFinding}</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t.reviews.titleAr}><Input dir="rtl" value={nf.title_ar} onChange={(e) => setNf({ ...nf, title_ar: e.target.value })} /></Field>
            <Field label={t.reviews.titleEn}><Input dir="ltr" value={nf.title_en} onChange={(e) => setNf({ ...nf, title_en: e.target.value })} /></Field>
            <Field label={t.reviews.severity}><Select value={nf.severity} onChange={(e) => setNf({ ...nf, severity: e.target.value })}>
              {["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"].map((s) => <option key={s} value={s}>{label("severity", s)}</option>)}</Select></Field>
            <Field label={t.common.status}><Select value={nf.category} onChange={(e) => setNf({ ...nf, category: e.target.value })}>
              {["OBSERVATION", "RISK", "GAP", "MISSING_INFORMATION", "REGULATORY"].map((c) => <option key={c} value={c}>{label("findingCat", c)}</option>)}</Select></Field>
            <Field label={t.assess.interpretation} className="sm:col-span-2"><Textarea rows={2} value={nf.interpretation_ar} onChange={(e) => setNf({ ...nf, interpretation_ar: e.target.value })} /></Field>
          </div>
          <div className="mt-3 flex justify-end">
            <Button size="sm" variant="secondary" disabled={!nf.title_ar || !nf.title_en} onClick={() => { setNewFindings([...newFindings, nf]); setNf({ ...nf, title_ar: "", title_en: "", interpretation_ar: "" }); }}><Plus />{t.reviews.addFinding}</Button>
          </div>
          {newFindings.length > 0 && <ul className="mt-3 flex flex-col gap-1 text-[13px]">{newFindings.map((f, i) => <li key={i} className="rounded bg-primary-soft/50 px-3 py-1.5">{f.title_ar} — {label("severity", f.severity)}</li>)}</ul>}
        </fieldset>
        <div className="flex justify-end gap-2 border-t border-line pt-4">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>{t.common.cancel}</Button>
          <Button loading={busy} onClick={() => onSave({ summary_ar: summaryAr, summary_en: summaryEn, analyst_notes: notes,
            new_findings: newFindings.map((f) => ({ ...f, interpretation_en: f.interpretation_ar, evidence_ar: "", evidence_en: "", citations: [] })) })}>{t.reviews.saveVersion}</Button>
        </div>
      </div>
    </Drawer>
  );
}
