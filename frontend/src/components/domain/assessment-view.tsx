"use client";

import { useQuery } from "@tanstack/react-query";
import { FileText, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { MockTag, OriginTag, RiskBadge, StatusBadge } from "@/components/domain/badges";
import { FindingItem } from "@/components/domain/finding";
import { Notice } from "@/components/ui/feedback";
import { DescList, Panel, TabPanel, Tabs } from "@/components/ui/layout";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { AppDocument, Draft, Finding } from "@/lib/types";

export const GROUPS = [
  { key: "GAP", cats: ["GAP"] }, { key: "RISK", cats: ["RISK", "OBSERVATION"] }, { key: "MISSING", cats: ["MISSING_INFORMATION"] }, { key: "REGULATORY", cats: ["REGULATORY"] },
] as const;

export function groupLabel(t: ReturnType<typeof useI18n>["t"], key: string) {
  return ({ GAP: t.assess.gaps, RISK: t.assess.risk, MISSING: t.assess.missing, REGULATORY: t.assess.regulatory } as Record<string, string>)[key];
}

/** Start column of the workspace: application facts, documents, extracted profile. */
export function ApplicationColumn({ draft }: { draft: Draft }) {
  const { t, pick, label, fmtNum } = useI18n();
  const a = draft.application;
  const docs = useQuery({ queryKey: ["documents", a.id], queryFn: () => api<AppDocument[]>(`/applications/${a.id}/documents`) });
  const missing = new Set(draft.missing_documents.map((m) => m.document_type));
  return (
    <div className="flex flex-col gap-5">
      <Panel title={t.assess.application} actions={<Link href={`/applications/${a.id}`} className="text-[12.5px] font-medium text-primary hover:underline">{t.common.open}</Link>}>
        <p className="text-[15px] font-semibold">{pick(a.company_name_ar, a.company_name_en)}</p>
        <p className="ltr mt-0.5 text-start text-[12px] text-muted">{a.reference}</p>
        <div className="mt-4"><DescList cols={1} items={[
          { label: t.apps.category, value: label("category", a.service_category) },
          { label: t.apps.capital, value: a.paid_up_capital_sar != null && <span className="num">{fmtNum(a.paid_up_capital_sar)}</span> },
          { label: t.apps.hosting, value: a.data_hosting_location },
          { label: t.apps.thirdParty, value: a.uses_third_party_providers ? t.common.yes : t.common.no },
        ]} /></div>
        <p className="mt-4 text-[12.5px] text-muted">{t.apps.businessModel}</p>
        <p className="mt-1 text-[13.5px] leading-relaxed text-ink-2">{a.business_model}</p>
      </Panel>
      <Panel title={t.apps.documents} bodyClass="p-0">
        <ul className="divide-y divide-line">
          {docs.data?.map((d) => (
            <li key={d.id} className="flex items-center gap-3 px-5 py-2.5 text-[13px]">
              <FileText className="size-4 text-muted" />{label("docType", d.document_type)}
            </li>
          ))}
          {draft.missing_documents.map((m) => (
            <li key={m.document_type} className="flex items-center gap-3 px-5 py-2.5 text-[13px] text-danger">
              <span className="size-4 rounded-full border-2 border-dashed border-danger-base" aria-hidden />{label("docType", m.document_type)}
              <span className="ms-auto text-[11.5px]">{t.assess.missingDocs}</span>
            </li>
          ))}
        </ul>
        {missing.size === 0 && <p className="px-5 pb-3 text-[12.5px] text-success">✓ {pick("جميع الوثائق المطلوبة مقدمة", "All required documents submitted")}</p>}
      </Panel>
      <Panel title={t.assess.profile}>
        {Object.keys(draft.extracted_profile).length === 0 ? <p className="text-[13px] text-muted">—</p> :
          <DescList cols={1} items={Object.entries(draft.extracted_profile).map(([k, v]) => ({ label: label("profile", k) === k ? k.replaceAll("_", " ") : label("profile", k),
            value: <span className="num">{typeof v === "number" ? fmtNum(v) : typeof v === "boolean" ? (v ? t.common.yes : t.common.no) : String(v)}</span> }))} />}
      </Panel>
    </div>
  );
}

export function DraftHeaderMeta({ draft }: { draft: Draft }) {
  const { t, fmtDate } = useI18n();
  return (
    <>
      <StatusBadge status={draft.status} group="draftStatus" />
      <span className="text-[13px] text-muted">{t.assess.versionN} <span className="num">{draft.version}</span> · {fmtDate(draft.created_at, true)}</span>
      <OriginTag origin={draft.authored_by} />
      <MockTag show={!!draft.generation_meta?.mock} />
    </>
  );
}

/** End column: summary, risk, findings grouped by type with their evidence thread. */
export function AssessmentColumn({ draft, findingActions }: { draft: Draft; findingActions?: (f: Finding) => React.ReactNode }) {
  const { t, pick, label, fmtNum } = useI18n();
  const counts = Object.fromEntries(GROUPS.map((g) => [g.key, draft.findings.filter((f) => (g.cats as readonly string[]).includes(f.category)).length]));
  const [tab, setTab] = useState<string>(GROUPS.find((g) => counts[g.key] > 0)?.key ?? "GAP");
  let citationIndex = 1;
  const injection = (draft.generation_meta?.injection_flags ?? []) as { filename: string }[];
  return (
    <div className="flex flex-col gap-5">
      <section className="rounded-xl border border-line bg-surface p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[12.5px] text-muted">{t.assess.overallRisk}</p>
            <div className="mt-1.5"><RiskBadge value={draft.overall_risk} /></div>
          </div>
          <dl className="flex gap-6 text-center">
            {GROUPS.map((g) => (
              <div key={g.key}><dt className="text-[11.5px] text-muted">{groupLabel(t, g.key)}</dt><dd className="text-[20px] font-semibold num">{fmtNum(counts[g.key])}</dd></div>
            ))}
          </dl>
        </div>
        <div className="mt-5 border-t border-line pt-4">
          <p className="text-[12.5px] font-medium text-muted">{t.assess.summary}</p>
          <p className="mt-1.5 text-[14.5px] leading-[1.9]">{pick(draft.summary_ar, draft.summary_en)}</p>
          {draft.analyst_notes && (
            <div className="mt-4 rounded-lg border border-primary/20 bg-primary-soft/40 px-4 py-3">
              <p className="text-[12px] font-medium text-primary">{t.reviews.analystNotes} — {pick(draft.edited_by_name_ar, draft.edited_by_name_en)}</p>
              <p className="mt-1 whitespace-pre-line text-[13.5px]">{draft.analyst_notes}</p>
            </div>
          )}
        </div>
        {injection.length > 0 && <Notice tone="warning" icon={ShieldAlert} className="mt-4">{t.assess.injectionWarning} <span className="ltr">({injection.map((i) => i.filename).join(", ")})</span></Notice>}
      </section>

      <Tabs value={tab} onValueChange={setTab} items={GROUPS.map((g) => ({ value: g.key, label: groupLabel(t, g.key), count: counts[g.key] }))}>
        {GROUPS.map((g) => {
          const items = draft.findings.filter((f) => (g.cats as readonly string[]).includes(f.category));
          return (
            <TabPanel key={g.key} value={g.key} className="flex flex-col gap-2.5">
              {items.length === 0 ? <p className="py-8 text-center text-[13px] text-muted">{t.assess.noFindings}</p> : items.map((f, i) => {
                const start = citationIndex;
                citationIndex += f.citations.length;
                return <FindingItem key={f.id} f={f} defaultOpen={i === 0} citationStart={start} actions={findingActions?.(f)} />;
              })}
            </TabPanel>
          );
        })}
      </Tabs>

      <section className="rounded-xl border border-line bg-canvas px-5 py-4">
        <p className="text-[12.5px] font-medium text-muted">{t.assess.limitations}</p>
        <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{pick(draft.limitations_ar, draft.limitations_en)}</p>
        <p className="mt-2 text-[12px] text-faint ltr text-start">{draft.generation_meta?.provider} / {draft.generation_meta?.model} · {draft.generation_meta?.embedding_model}</p>
      </section>

      <Panel title={t.assess.analystComments}>
        {draft.reviews.length === 0 ? <p className="text-[13px] text-muted">{t.assess.noComments}</p> : (
          <ul className="flex flex-col gap-3">
            {draft.reviews.map((r) => (
              <li key={r.id} className="border-s-2 border-line-strong ps-3">
                <p className="text-[12.5px] text-muted"><span className="font-medium text-ink-2">{pick(r.reviewer_name_ar, r.reviewer_name_en)}</span> · {label("decision", r.decision)}</p>
                {r.comment && <p className="mt-0.5 text-[13.5px]">{r.comment}</p>}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
