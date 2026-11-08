"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpenText, Lock, Upload } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";
import { SyntheticTag } from "@/components/domain/badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Drawer } from "@/components/ui/dialog";
import { Checkbox, Field, Input, Select } from "@/components/ui/field";
import { EmptyState, ErrorState, Notice, SkeletonRows } from "@/components/ui/feedback";
import { PageHeader, TabPanel, Tabs } from "@/components/ui/layout";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { api, errorText } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { Severity } from "@/components/domain/badges";

type Version = { id: string; version_label: string; status: string; page_count: number; chunk_count: number; indexing_status: string;
  publication_date: string | null; effective_date: string | null; filename: string; content_type: string; created_at: string; extracted_metadata: Record<string, any>; sha256: string };
type Doc = { id: string; document_code: string; title_ar: string; title_en: string; source: string; language: string; classification: string;
  is_synthetic: boolean; tags: string[]; current_version: Version | null; version_count: number; updated_at: string };
type Req = { id: string; code: string; title_ar: string; title_en: string; service_categories: string[]; required_document_types: string[];
  rule: Record<string, any>; severity: string; source_document_code: string; source_section: string; is_synthetic: boolean; active: boolean };

const CLASS_TONE = { public: "success", internal: "primary", restricted: "danger" } as const;

export default function Knowledge() {
  const { t, pick, fmtDate, fmtNum, label } = useI18n();
  const { can } = useAuth();
  const [tab, setTab] = useState("documents");
  const [uploadOpen, setUploadOpen] = useState(false);
  const docs = useQuery({ queryKey: ["regdocs"], queryFn: () => api<{ items: Doc[]; restricted_hidden: number }>("/regulatory/documents") });
  const reqs = useQuery({ queryKey: ["requirements"], queryFn: () => api<Req[]>("/regulatory/requirements") });

  return (
    <div>
      <PageHeader title={t.kb.title} subtitle={t.kb.subtitle}
        actions={can("regulatory:manage") && <Button onClick={() => setUploadOpen(true)}><Upload />{t.kb.upload}</Button>} />
      <Tabs value={tab} onValueChange={setTab} items={[{ value: "documents", label: t.kb.documents, count: docs.data?.items.length }, { value: "requirements", label: t.kb.requirements, count: reqs.data?.length }]}>
        <TabPanel value="documents">
          {docs.isError ? <ErrorState error={docs.error} onRetry={() => docs.refetch()} /> : !docs.data ? <SkeletonRows /> :
            docs.data.items.length === 0 ? <EmptyState icon={BookOpenText} title={t.common.emptyTitle} /> : (
              <>
                <ul className="grid gap-3 lg:grid-cols-2">
                  {docs.data.items.map((d) => (
                    <li key={d.id}>
                      <Link href={`/knowledge/${d.id}`} className="flex h-full flex-col gap-3 rounded-xl border border-line bg-surface p-5 hover:border-primary/40">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="ltr text-start text-[12px] font-medium text-muted">{d.document_code}</p>
                            <h3 className="mt-0.5 text-[14.5px] font-semibold leading-snug">{pick(d.title_ar, d.title_en) || d.title_en}</h3>
                          </div>
                          <Badge tone={CLASS_TONE[d.classification as keyof typeof CLASS_TONE] ?? "neutral"}>
                            {d.classification === "restricted" && <Lock className="size-3" />}{(t.kb as Record<string, string>)[d.classification]}
                          </Badge>
                        </div>
                        <div className="mt-auto flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line pt-3 text-[12.5px] text-muted">
                          <span>{t.common.version} <span className="ltr text-ink-2">{d.current_version?.version_label}</span></span>
                          <span className="num">{fmtNum(d.current_version?.chunk_count ?? 0)} {t.kb.chunks}</span>
                          <span>{t.kb.effective}: {d.current_version?.effective_date ? fmtDate(d.current_version.effective_date) : t.kb.notSupplied}</span>
                          {d.version_count > 1 && <span className="num">{fmtNum(d.version_count)} {t.kb.versions}</span>}
                          {d.is_synthetic && <SyntheticTag />}
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
                {docs.data.restricted_hidden > 0 && <p className="mt-3 flex items-center gap-1.5 text-[12.5px] text-muted"><Lock className="size-3.5" /><span className="num">{fmtNum(docs.data.restricted_hidden)}</span> {t.kb.restrictedHidden}</p>}
              </>
            )}
        </TabPanel>
        <TabPanel value="requirements">
          <Notice tone="info" className="mb-4">{t.kb.configuredNote}</Notice>
          <div className="rounded-xl border border-line bg-surface">
            {!reqs.data ? <SkeletonRows className="p-5" /> : (
              <Table>
                <thead><tr><Th>{t.kb.requirement}</Th><Th>{t.kb.appliesTo}</Th><Th>{t.kb.requiredDocs}</Th><Th>{t.kb.rule}</Th><Th>{t.kb.severity}</Th><Th>{t.kb.sourceSection}</Th></tr></thead>
                <tbody>
                  {reqs.data.map((r) => (
                    <Tr key={r.id}>
                      <Td><p className="font-medium">{pick(r.title_ar, r.title_en)}</p><p className="ltr text-start text-[12px] text-muted">{r.code}</p></Td>
                      <Td className="text-[12.5px] text-ink-2">{r.service_categories.length ? r.service_categories.map((c) => label("category", c)).join("، ") : t.kb.allCategories}</Td>
                      <Td className="text-[12.5px] text-ink-2">{r.required_document_types.map((d) => label("docType", d)).join("، ") || "—"}</Td>
                      <Td>{r.rule?.field ? <code className="ltr rounded bg-surface-2 px-1.5 py-0.5 text-[12px]">{r.rule.field} {r.rule.op} {fmtNum(r.rule.value)}</code> : "—"}</Td>
                      <Td><Severity value={r.severity} /></Td>
                      <Td className="text-[12.5px]"><span className="ltr text-muted">{r.source_document_code}</span><p>{r.source_section}</p></Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            )}
          </div>
        </TabPanel>
      </Tabs>
      <UploadDrawer open={uploadOpen} onOpenChange={setUploadOpen} />
    </div>
  );
}

function UploadDrawer({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const { t, locale } = useI18n();
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [v, setV] = useState({ document_code: "", title_ar: "", title_en: "", source: "", classification: "internal", version_label: "", publication_date: "", effective_date: "", tags: "", is_synthetic: true });
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    Object.entries(v).forEach(([k, val]) => { if (val !== "") fd.append(k, String(val)); });
    setBusy(true);
    try {
      await api("/regulatory/documents", { form: fd });
      toast.success(t.kb.uploadedToast);
      qc.invalidateQueries({ queryKey: ["regdocs"] });
      onOpenChange(false);
      setFile(null);
    } catch (e) { toast.error(errorText(e, locale)); } finally { setBusy(false); }
  };
  return (
    <Drawer open={open} onOpenChange={onOpenChange} title={t.kb.upload} subtitle={t.kb.newVersionHint}>
      <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); submit(); }}>
        <Field label={t.kb.code} required htmlFor="code"><Input id="code" dir="ltr" required value={v.document_code} onChange={(e) => setV({ ...v, document_code: e.target.value })} /></Field>
        <Field label={t.kb.classification} htmlFor="cls"><Select id="cls" value={v.classification} onChange={(e) => setV({ ...v, classification: e.target.value })}>
          <option value="public">{t.kb.public}</option><option value="internal">{t.kb.internal}</option><option value="restricted">{t.kb.restricted}</option></Select></Field>
        <Field label={t.kb.titleAr} htmlFor="tar" className="sm:col-span-2"><Input id="tar" value={v.title_ar} onChange={(e) => setV({ ...v, title_ar: e.target.value })} /></Field>
        <Field label={t.kb.titleEn} htmlFor="ten" className="sm:col-span-2"><Input id="ten" dir="ltr" value={v.title_en} onChange={(e) => setV({ ...v, title_en: e.target.value })} /></Field>
        <Field label={t.kb.source} htmlFor="src"><Input id="src" value={v.source} onChange={(e) => setV({ ...v, source: e.target.value })} /></Field>
        <Field label={t.kb.versionLabel} htmlFor="vl"><Input id="vl" dir="ltr" value={v.version_label} onChange={(e) => setV({ ...v, version_label: e.target.value })} /></Field>
        <Field label={t.kb.publication} hint={t.common.optional} htmlFor="pd"><Input id="pd" type="date" value={v.publication_date} onChange={(e) => setV({ ...v, publication_date: e.target.value })} /></Field>
        <Field label={t.kb.effective} hint={t.common.optional} htmlFor="ed"><Input id="ed" type="date" value={v.effective_date} onChange={(e) => setV({ ...v, effective_date: e.target.value })} /></Field>
        <Field label={t.kb.tags} htmlFor="tags" className="sm:col-span-2"><Input id="tags" value={v.tags} onChange={(e) => setV({ ...v, tags: e.target.value })} /></Field>
        <div className="sm:col-span-2"><Checkbox label={t.kb.synthetic} checked={v.is_synthetic} onChange={(x) => setV({ ...v, is_synthetic: x })} /></div>
        <label className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-line-strong bg-canvas px-4 py-7 text-center hover:border-primary/50 sm:col-span-2">
          <Upload className="size-5 text-muted" />
          <span className="text-[13px] text-ink-2">{file ? <span className="ltr">{file.name}</span> : t.apps.chooseFile}</span>
          <input type="file" accept=".pdf,.docx,.txt" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>{t.common.cancel}</Button>
          <Button type="submit" loading={busy} disabled={!file || !v.document_code}>{t.common.upload}</Button>
        </div>
      </form>
    </Drawer>
  );
}
