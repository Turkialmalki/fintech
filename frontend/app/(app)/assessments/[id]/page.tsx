"use client";

import { useQuery } from "@tanstack/react-query";
import { ClipboardCheck, FileDown } from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";
import { toast } from "sonner";
import { ApplicationColumn, AssessmentColumn, DraftHeaderMeta } from "@/components/domain/assessment-view";
import { Button } from "@/components/ui/button";
import { ErrorState, Notice, SkeletonRows } from "@/components/ui/feedback";
import { PageHeader } from "@/components/ui/layout";
import { api, errorText, openPdf } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { Draft } from "@/lib/types";

export default function Workspace({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t, pick, locale } = useI18n();
  const { can } = useAuth();
  const q = useQuery({ queryKey: ["draft", id], queryFn: () => api<Draft>(`/assessments/${id}`) });
  const [pdf, setPdf] = useState<string | null>(null);
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data;
  if (!d) return <SkeletonRows rows={10} />;
  const exportPdf = async (lang: "ar" | "en") => {
    setPdf(lang);
    try { await openPdf(`/assessments/${id}/report.pdf?lang=${lang}`); } catch (e) { toast.error(errorText(e, locale)); } finally { setPdf(null); }
  };
  return (
    <div>
      <PageHeader title={t.assess.workspace} crumbs={[{ label: t.assess.title, href: "/assessments" }, { label: pick(d.application.company_name_ar, d.application.company_name_en) }]}
        meta={<DraftHeaderMeta draft={d} />}
        actions={<>
          <Button variant="secondary" loading={pdf === "ar"} onClick={() => exportPdf("ar")}><FileDown />{t.assess.exportAr}</Button>
          <Button variant="secondary" loading={pdf === "en"} onClick={() => exportPdf("en")}><FileDown />{t.assess.exportEn}</Button>
          {can("reviews:write") && <Button asChild><Link href={`/reviews/${id}`}><ClipboardCheck />{t.assess.reviewAction}</Link></Button>}
        </>} />
      <Notice tone="info" className="mb-6">{t.assess.disclaimer}</Notice>
      {d.status === "SUPERSEDED" && (
        <Notice tone="warning" className="mb-6">{pick("هذا إصدار سابق من التقييم.", "This is a superseded version of the assessment.")}{" "}
          <Link className="font-medium underline" href={`/assessments/${d.versions[0].id}`}>{pick("فتح أحدث إصدار", "Open latest version")}</Link></Notice>
      )}
      <div className="grid gap-6 xl:grid-cols-[minmax(300px,0.8fr)_minmax(0,1.7fr)]">
        <aside className="xl:sticky xl:top-24 xl:max-h-[calc(100dvh-7rem)] xl:self-start xl:overflow-y-auto scroll-thin"><ApplicationColumn draft={d} /></aside>
        <AssessmentColumn draft={d} />
      </div>
    </div>
  );
}
