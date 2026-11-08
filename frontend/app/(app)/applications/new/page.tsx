"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ApplicationForm } from "@/components/domain/application-form";
import { PageHeader } from "@/components/ui/layout";
import { api, errorText } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Application } from "@/lib/types";

export default function NewApplication() {
  const { t, locale } = useI18n();
  const router = useRouter();
  const qc = useQueryClient();
  return (
    <div className="max-w-5xl">
      <PageHeader title={t.apps.new} subtitle={t.apps.formIntro} crumbs={[{ label: t.apps.title, href: "/applications" }, { label: t.apps.new }]} />
      <div className="rounded-xl border border-line bg-surface p-6 md:p-8">
        <ApplicationForm submitLabel={t.apps.create} onCancel={() => router.back()}
          onSubmit={async (v) => {
            try {
              const a = await api<Application>("/applications", { body: v });
              toast.success(t.apps.createdToast, { description: a.reference });
              qc.invalidateQueries({ queryKey: ["applications"] });
              router.push(`/applications/${a.id}`);
            } catch (e) { toast.error(errorText(e, locale)); }
          }} />
      </div>
    </div>
  );
}
