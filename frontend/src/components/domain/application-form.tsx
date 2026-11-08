"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Checkbox, Field, Input, Select, Textarea } from "@/components/ui/field";
import { labels } from "@/lib/dictionaries";
import { useI18n } from "@/lib/i18n";
import type { Application } from "@/lib/types";

const CATS = ["BNPL", "DIGITAL_PAYMENTS", "OPEN_BANKING", "LENDING", "DIGITAL_WALLET"] as const;

export function makeSchema(pick: <T>(a: T, b: T) => T) {
  const num = z.union([z.literal(""), z.coerce.number().min(0, pick("يجب أن تكون القيمة موجبة", "Must be positive"))]).optional();
  return z.object({
    company_name_ar: z.string().trim().min(2, pick("أدخل اسم الشركة بالعربية", "Enter the Arabic company name")),
    company_name_en: z.string().trim().min(2, pick("أدخل اسم الشركة بالإنجليزية", "Enter the English company name")),
    commercial_registration: z.string().trim().regex(/^(\d{10})?$/, pick("رقم السجل التجاري مكون من 10 أرقام", "CR number has 10 digits")),
    city: z.string().max(80).optional(),
    contact_email: z.union([z.literal(""), z.string().email(pick("بريد إلكتروني غير صحيح", "Invalid email"))]).optional(),
    website: z.string().max(255).optional(),
    service_category: z.enum(CATS, { message: pick("اختر فئة الخدمة", "Choose a service category") }),
    business_model: z.string().max(5000).optional(),
    target_customers: z.string().max(2000).optional(),
    paid_up_capital_sar: num,
    expected_monthly_volume_sar: num,
    data_hosting_location: z.string().max(80).optional(),
    uses_third_party_providers: z.boolean(),
  });
}

export type AppFormValues = z.infer<ReturnType<typeof makeSchema>>;

export function toPayload(v: AppFormValues) {
  const n = (x: unknown) => (x === "" || x === undefined ? null : Number(x));
  return { ...v, contact_email: v.contact_email || null, paid_up_capital_sar: n(v.paid_up_capital_sar), expected_monthly_volume_sar: n(v.expected_monthly_volume_sar) };
}

export function ApplicationForm({ initial, onSubmit, submitLabel, onCancel }: {
  initial?: Partial<Application>; onSubmit: (v: ReturnType<typeof toPayload>) => Promise<void>; submitLabel: string; onCancel?: () => void;
}) {
  const { t, pick, label } = useI18n();
  const schema = makeSchema(pick);
  const { register, handleSubmit, watch, setValue, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      company_name_ar: initial?.company_name_ar ?? "", company_name_en: initial?.company_name_en ?? "",
      commercial_registration: initial?.commercial_registration ?? "", city: initial?.city ?? "", contact_email: initial?.contact_email ?? "",
      website: initial?.website ?? "", service_category: (initial?.service_category as AppFormValues["service_category"]) ?? undefined,
      business_model: initial?.business_model ?? "", target_customers: initial?.target_customers ?? "",
      paid_up_capital_sar: (initial?.paid_up_capital_sar ?? "") as never, expected_monthly_volume_sar: (initial?.expected_monthly_volume_sar ?? "") as never,
      data_hosting_location: initial?.data_hosting_location ?? "", uses_third_party_providers: initial?.uses_third_party_providers ?? false,
    },
  });
  const err = (k: keyof AppFormValues) => errors[k]?.message as string | undefined;

  const Section = ({ title, children }: { title: string; children: React.ReactNode }) => (
    <fieldset className="grid gap-x-6 gap-y-5 border-t border-line pt-6 first:border-t-0 first:pt-0 md:grid-cols-[200px_minmax(0,1fr)]">
      <legend className="contents"><span className="text-[14px] font-semibold text-ink">{title}</span></legend>
      <div className="grid gap-5 sm:grid-cols-2">{children}</div>
    </fieldset>
  );

  return (
    <form onSubmit={handleSubmit(async (v) => onSubmit(toPayload(v as AppFormValues)))} className="flex flex-col gap-8" noValidate>
      <Section title={t.apps.sectionCompany}>
        <Field label={t.apps.companyAr} htmlFor="company_name_ar" required error={err("company_name_ar")}>
          <Input id="company_name_ar" dir="rtl" aria-invalid={!!errors.company_name_ar} {...register("company_name_ar")} />
        </Field>
        <Field label={t.apps.companyEn} htmlFor="company_name_en" required error={err("company_name_en")}>
          <Input id="company_name_en" dir="ltr" aria-invalid={!!errors.company_name_en} {...register("company_name_en")} />
        </Field>
        <Field label={t.apps.cr} htmlFor="cr" error={err("commercial_registration")}>
          <Input id="cr" dir="ltr" inputMode="numeric" maxLength={10} aria-invalid={!!errors.commercial_registration} {...register("commercial_registration")} />
        </Field>
        <Field label={t.apps.city} htmlFor="city"><Input id="city" {...register("city")} /></Field>
        <Field label={t.apps.email} htmlFor="email" error={err("contact_email")}>
          <Input id="email" type="email" dir="ltr" aria-invalid={!!errors.contact_email} {...register("contact_email")} />
        </Field>
        <Field label={t.apps.website} htmlFor="website"><Input id="website" dir="ltr" placeholder="https://" {...register("website")} /></Field>
      </Section>
      <Section title={t.apps.sectionService}>
        <Field label={t.apps.category} htmlFor="cat" required error={err("service_category")} className="sm:col-span-2">
          <Select id="cat" aria-invalid={!!errors.service_category} {...register("service_category")}>
            <option value="">{pick("اختر…", "Choose…")}</option>
            {Object.keys(labels.category).map((c) => <option key={c} value={c}>{label("category", c)}</option>)}
          </Select>
        </Field>
        <Field label={t.apps.businessModel} htmlFor="bm" className="sm:col-span-2"><Textarea id="bm" rows={4} {...register("business_model")} /></Field>
        <Field label={t.apps.targetCustomers} htmlFor="tc" className="sm:col-span-2"><Textarea id="tc" rows={2} {...register("target_customers")} /></Field>
      </Section>
      <Section title={t.apps.sectionFinancial}>
        <Field label={t.apps.capital} htmlFor="cap" error={err("paid_up_capital_sar")}>
          <Input id="cap" type="number" min={0} step="any" dir="ltr" {...register("paid_up_capital_sar")} />
        </Field>
        <Field label={t.apps.volume} htmlFor="vol" error={err("expected_monthly_volume_sar")}>
          <Input id="vol" type="number" min={0} step="any" dir="ltr" {...register("expected_monthly_volume_sar")} />
        </Field>
        <Field label={t.apps.hosting} htmlFor="host"><Input id="host" {...register("data_hosting_location")} /></Field>
        <div className="flex items-end pb-1.5">
          <Checkbox label={t.apps.thirdParty} checked={!!watch("uses_third_party_providers")} onChange={(v) => setValue("uses_third_party_providers", v)} />
        </div>
      </Section>
      <div className="flex justify-end gap-2 border-t border-line pt-5">
        {onCancel && <Button type="button" variant="secondary" onClick={onCancel}>{t.common.cancel}</Button>}
        <Button type="submit" loading={isSubmitting}>{submitLabel}</Button>
      </div>
    </form>
  );
}
