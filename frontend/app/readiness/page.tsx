"use client";

import {
  ArrowLeft, ArrowRight, Banknote, Check, ChevronDown, CreditCard, ExternalLink, FileText, Landmark, Languages, Link2, ListChecks,
  Printer, RotateCcw, ShieldAlert, Trash2, TriangleAlert, Upload, Wallet, X,
} from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { ProductPreview, ScoreRing } from "@/components/marketing/preview";
import { LogoMark } from "@/components/shell/logo";
import { Button } from "@/components/ui/button";
import { Checkbox, Field, Input, Select, Textarea } from "@/components/ui/field";
import { Notice } from "@/components/ui/feedback";
import { api, errorText } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Evidence = { document_code: string; title_ar: string; title_en: string; section: string; text: string; source_url: string } | null;
type Req = { code: string; title_ar: string; title_en: string; severity: string; outcome: "MET" | "POTENTIAL_GAP" | "INSUFFICIENT_INFORMATION";
  missing_documents: string[]; action_ar: string; evidence: Evidence };
type Missing = { key: string; label_ar: string; label_en: string };
type Analysed = { filename: string; detected_type: string; assigned_types: string[]; pages: number; size_bytes: number;
  status: "ACCEPTED" | "PARTIAL" | "REJECTED"; reason_ar: string; reason_en: string; elements_found: string[]; elements_missing: Missing[];
  suspicious_instructions: boolean };
type Result = {
  company_name: string; service_category: string; score: number; level: "HIGH" | "MEDIUM" | "LOW";
  counts: { met: number; gaps: number; insufficient: number; risks: number };
  requirements: Req[]; risks: { code: string; severity: string; title_ar: string; title_en: string; observed_value: unknown }[];
  key_rules: { text_ar: string; text_en: string; evidence: Evidence }[];
  documents: { analysed: Analysed[]; required: string[]; present: string[]; missing: string[] };
  consistency: { ar: string; en: string }[];
  capital_used: number | null; next_steps: string[]; notice_ar: string; notice_en: string;
};

const CATS = [
  { v: "BNPL", icon: CreditCard, d: ["تقسيط المشتريات دون تكلفة على العميل", "Split purchases at no cost to the consumer"] },
  { v: "DIGITAL_PAYMENTS", icon: Banknote, d: ["بوابات دفع وتحويلات ومدفوعات التجار", "Gateways, transfers and merchant payments"] },
  { v: "DIGITAL_WALLET", icon: Wallet, d: ["محافظ رقمية وإصدار النقود الإلكترونية", "Digital wallets and e-money issuance"] },
  { v: "OPEN_BANKING", icon: Link2, d: ["معلومات الحسابات وبدء الدفع", "Account information and payment initiation"] },
  { v: "LENDING", icon: Landmark, d: ["تمويل استهلاكي مصغر وتمويل جماعي بالدين", "Consumer microfinance and debt crowdfunding"] },
] as const;

const DOC_TYPES = ["COMMERCIAL_REGISTRATION", "BUSINESS_PLAN", "FINANCIAL_STATEMENTS", "AML_CTF_POLICY", "CYBERSECURITY_POLICY", "DATA_PROTECTION_POLICY",
  "GOVERNANCE_STRUCTURE", "OUTSOURCING_AGREEMENTS", "CONSUMER_PROTECTION_POLICY", "RISK_MANAGEMENT_FRAMEWORK", "OTHER"];

const LEVEL = {
  HIGH: { ar: "جاهزية مرتفعة", en: "High readiness", color: "#15966A", soft: "bg-success-soft text-success" },
  MEDIUM: { ar: "جاهزية متوسطة", en: "Moderate readiness", color: "#D99024", soft: "bg-warning-soft text-warning" },
  LOW: { ar: "جاهزية منخفضة", en: "Low readiness", color: "#D94B52", soft: "bg-danger-soft text-danger" },
};

function EvidenceBox({ e }: { e: Evidence }) {
  const { pick } = useI18n();
  if (!e) return null;
  return (
    <div className="mt-3 rounded-lg border-s-2 border-primary bg-surface-2/60 px-4 py-3">
      <p className="text-[13px] leading-relaxed text-ink-2">{e.text}</p>
      <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-muted">
        <span className="font-medium text-ink-2">{pick(e.title_ar, e.title_en)}</span><span>{e.section}</span>
        {e.source_url && (
          <a href={e.source_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline">
            <ExternalLink className="size-3" />{pick("المصدر الرسمي", "Official source")}
          </a>
        )}
      </p>
    </div>
  );
}

function ReqRow({ r }: { r: Req }) {
  const { pick, label } = useI18n();
  const [open, setOpen] = useState(r.outcome !== "MET");
  const meta = {
    MET: { icon: Check, cls: "bg-success-soft text-success", t: pick("مستوفى", "Met") },
    POTENTIAL_GAP: { icon: X, cls: "bg-danger-soft text-danger", t: pick("فجوة", "Gap") },
    INSUFFICIENT_INFORMATION: { icon: TriangleAlert, cls: "bg-warning-soft text-warning", t: pick("معلومات ناقصة", "Needs info") },
  }[r.outcome];
  return (
    <li className="rounded-xl border border-line bg-surface">
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-start gap-3 px-4 py-3.5 text-start" aria-expanded={open}>
        <span className={cn("mt-0.5 grid size-7 shrink-0 place-items-center rounded-full", meta.cls)}><meta.icon className="size-4" strokeWidth={2.5} /></span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-[14.5px] font-medium">{pick(r.title_ar, r.title_en)}</span>
            <span className={cn("rounded-full px-2 py-px text-[11.5px] font-medium", meta.cls)}>{meta.t}</span>
            {r.outcome !== "MET" && <span className="text-[11.5px] text-muted">{pick("الأهمية:", "Severity:")} {label("severity", r.severity)}</span>}
          </span>
          {r.action_ar && <span className="mt-1 block text-[13px] text-ink-2">{r.action_ar}</span>}
          {r.outcome === "POTENTIAL_GAP" && r.missing_documents.length > 0 && !r.action_ar && (
            <span className="mt-1 block text-[13px] text-ink-2">{r.missing_documents.map((d) => label("docType", d)).join("، ")}</span>
          )}
        </span>
        <ChevronDown className={cn("mt-1 size-4 shrink-0 text-muted transition-transform", open && "rotate-180")} />
      </button>
      {open && <div className="px-4 pb-4 ps-14"><EvidenceBox e={r.evidence} /></div>}
    </li>
  );
}

function DocChecks({ docs }: { docs: Analysed[] }) {
  const { pick, label } = useI18n();
  const meta = {
    ACCEPTED: { t: pick("مقبولة", "Accepted"), cls: "bg-success-soft text-success", icon: Check },
    PARTIAL: { t: pick("غير مكتملة", "Incomplete"), cls: "bg-warning-soft text-warning", icon: TriangleAlert },
    REJECTED: { t: pick("مرفوضة", "Rejected"), cls: "bg-danger-soft text-danger", icon: X },
  };
  const n = (s: string) => docs.filter((d) => d.status === s).length;
  return (
    <section>
      <h2 className="flex items-center gap-2 text-[17px] font-semibold"><FileText className="size-5 text-primary" />{pick("التحقق من الوثائق المرفوعة", "Uploaded document checks")}</h2>
      <p className="mt-1 text-[13px] text-muted">{pick(`${n("ACCEPTED")} مقبولة · ${n("PARTIAL")} غير مكتملة · ${n("REJECTED")} مرفوضة. الوثائق المرفوضة لا تُحتسب في النتيجة.`,
        `${n("ACCEPTED")} accepted · ${n("PARTIAL")} incomplete · ${n("REJECTED")} rejected. Rejected files are not counted.`)}</p>
      <ul className="mt-3 flex flex-col gap-2.5">
        {docs.map((d, i) => {
          const m = meta[d.status];
          return (
            <li key={i} className="rounded-xl border border-line bg-surface px-4 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className={cn("grid size-6 place-items-center rounded-full", m.cls)}><m.icon className="size-3.5" strokeWidth={2.5} /></span>
                <span className="ltr truncate text-[13.5px] font-medium">{d.filename}</span>
                <span className={cn("rounded-full px-2 py-px text-[11.5px] font-medium", m.cls)}>{m.t}</span>
                {d.assigned_types.length > 0 && <span className="text-[12.5px] text-muted">{d.assigned_types.map((x) => label("docType", x)).join("، ")}</span>}
              </div>
              {d.reason_ar && <p className="mt-1.5 text-[13px] text-ink-2">{pick(d.reason_ar, d.reason_en)}</p>}
              {d.status !== "REJECTED" && d.elements_missing.length > 0 && (
                <p className="mt-1.5 text-[12.5px] text-muted">{pick("عناصر لم نجدها:", "Elements not found:")} {d.elements_missing.map((x) => pick(x.label_ar, x.label_en)).join("، ")}</p>
              )}
              {d.suspicious_instructions && <p className="mt-1 text-[12.5px] text-warning">{pick("تحتوي على تعليمات مضمّنة مشبوهة وتم تجاهلها", "Contains embedded instructions, which were ignored")}</p>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default function ReadinessPage() {
  const { t, pick, label, locale, setLocale, fmtNum } = useI18n();
  const Arrow = locale === "ar" ? ArrowLeft : ArrowRight;
  const [cat, setCat] = useState<string>("BNPL");
  const [f, setF] = useState({ company_name: "", description: "", capital: "", volume: "", hosting: "", third: false });
  const [files, setFiles] = useState<{ file: File; type: string }[]>([]);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [res, setRes] = useState<Result | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const top = useRef<HTMLDivElement>(null);

  const [fileErr, setFileErr] = useState<string[]>([]);
  const addFiles = (list: FileList | null) => {
    if (!list) return;
    const errs: string[] = [];
    const ok: File[] = [];
    for (const x of Array.from(list)) {
      if (!/\.(pdf|docx|txt)$/i.test(x.name)) errs.push(pick(`${x.name}: نوع غير مدعوم — PDF أو DOCX أو TXT فقط`, `${x.name}: unsupported type — PDF, DOCX or TXT only`));
      else if (x.size === 0) errs.push(pick(`${x.name}: الملف فارغ`, `${x.name}: the file is empty`));
      else if (x.size > 8 * 1024 * 1024) errs.push(pick(`${x.name}: يتجاوز 8 ميجابايت`, `${x.name}: larger than 8 MB`));
      else if (files.some((f) => f.file.name === x.name && f.file.size === x.size)) errs.push(pick(`${x.name}: مضاف مسبقاً`, `${x.name}: already added`));
      else ok.push(x);
    }
    if (files.length + ok.length > 10) errs.push(pick("الحد الأقصى 10 ملفات", "At most 10 files"));
    setFileErr(errs);
    setFiles((cur) => [...cur, ...ok.map((file) => ({ file, type: "AUTO" }))].slice(0, 10));
  };

  const submit = async () => {
    setErr(null); setBusy(true);
    const fd = new FormData();
    fd.set("service_category", cat);
    fd.set("company_name", f.company_name);
    fd.set("description", f.description);
    if (f.capital) fd.set("paid_up_capital_sar", f.capital.replace(/[,\s]/g, ""));
    if (f.volume) fd.set("expected_monthly_volume_sar", f.volume.replace(/[,\s]/g, ""));
    fd.set("data_hosting_location", f.hosting);
    fd.set("uses_third_party_providers", String(f.third));
    fd.set("document_types", files.map((x) => x.type).join(","));
    files.forEach((x) => fd.append("files", x.file));
    try {
      const r = await api<Result>("/readiness/check", { form: fd });
      setRes(r);
      setTimeout(() => top.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    } catch (e) {
      setErr(errorText(e, locale));
    } finally { setBusy(false); }
  };

  const gaps = res?.requirements.filter((r) => r.outcome !== "MET") ?? [];
  const met = res?.requirements.filter((r) => r.outcome === "MET") ?? [];
  const lv = res ? LEVEL[res.level] : null;

  return (
    <div className="min-h-dvh bg-canvas">
      <header className="sticky top-0 z-20 border-b border-line bg-surface/85 backdrop-blur-md print:hidden">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-5">
          <Link href="/readiness" className="flex items-center gap-2.5"><LogoMark size={30} /><span className="text-[14.5px] font-semibold">{t.brand.name}</span></Link>
          <div className="ms-auto flex items-center gap-1.5">
            <Button variant="ghost" size="sm" onClick={() => setLocale(locale === "ar" ? "en" : "ar")}><Languages />{t.common.language}</Button>
            <Button asChild variant="secondary" size="sm"><Link href="/login">{t.login.submit}</Link></Button>
          </div>
        </div>
      </header>

      {!res && (
        <section className="relative overflow-hidden bg-[#0d1830] text-white print:hidden">
          <div className="absolute inset-0 opacity-[0.06]" aria-hidden
            style={{ backgroundImage: "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)", backgroundSize: "40px 40px" }} />
          <div className="relative mx-auto grid max-w-6xl items-center gap-10 px-5 py-14 lg:grid-cols-[1fr_minmax(0,500px)] lg:py-20">
            <div className="animate-rise">
              <p className="text-[13px] font-medium text-[#9fb4e8]">{pick("مجاني · دون تسجيل · لا تُحفظ ملفاتك", "Free · No sign-up · Files are not stored")}</p>
              <h1 className="mt-3 text-[34px] font-semibold leading-[1.25] tracking-[-0.01em] sm:text-[40px]">{pick("هل شركتك جاهزة للترخيص؟", "Is your fintech ready for licensing?")}</h1>
              <p className="mt-4 max-w-[540px] text-[15.5px] leading-relaxed text-white/70">
                {pick("صِف نشاطك وارفع وثائقك، ونطابقها مع متطلبات البنك المركزي السعودي ونظام حماية البيانات الشخصية وأنظمة مكافحة غسل الأموال. تحصل على نسبة جاهزية وقائمة بالفجوات والوثائق الناقصة والخطوات التالية، مع رابط للنص الرسمي لكل متطلب.",
                  "Describe your activity and upload your documents. We match them against SAMA rules, the Personal Data Protection Law and AML requirements, and return a readiness score, gaps, missing documents and next steps — each linked to the official text.")}
              </p>
              <a href="#check" className="mt-7 inline-flex h-11 items-center gap-2 rounded-lg bg-white px-5 text-[15px] font-medium text-[#0d1830] hover:bg-white/90">
                {pick("ابدأ الفحص", "Start the check")}<Arrow className="size-[18px]" />
              </a>
            </div>
            <div className="hidden lg:block"><ProductPreview /></div>
          </div>
        </section>
      )}

      <main ref={top} className="mx-auto max-w-6xl scroll-mt-20 px-5 py-10">
        {!res ? (
          <div id="check" className="mx-auto max-w-3xl scroll-mt-24">
            <ol className="flex flex-col gap-8">
              <li>
                <h2 className="flex items-center gap-2 text-[17px] font-semibold"><span className="grid size-6 place-items-center rounded-full bg-primary text-[12px] text-white">1</span>{pick("ما نشاطك؟", "What is your activity?")}</h2>
                <div className="mt-4 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3" role="radiogroup">
                  {CATS.map((c) => (
                    <button key={c.v} type="button" role="radio" aria-checked={cat === c.v} onClick={() => setCat(c.v)}
                      className={cn("flex items-start gap-3 rounded-xl border bg-surface p-3.5 text-start transition-colors",
                        cat === c.v ? "border-primary ring-[3px] ring-primary/15" : "border-line hover:border-line-strong")}>
                      <span className={cn("grid size-9 shrink-0 place-items-center rounded-lg", cat === c.v ? "bg-primary text-white" : "bg-surface-2 text-ink-2")}><c.icon className="size-[18px]" /></span>
                      <span><span className="block text-[14px] font-medium">{label("category", c.v)}</span><span className="mt-0.5 block text-[12.5px] leading-snug text-muted">{pick(c.d[0], c.d[1])}</span></span>
                    </button>
                  ))}
                </div>
              </li>

              <li>
                <h2 className="flex items-center gap-2 text-[17px] font-semibold"><span className="grid size-6 place-items-center rounded-full bg-primary text-[12px] text-white">2</span>{pick("عن شركتك", "About your company")}</h2>
                <div className="mt-4 grid gap-4 rounded-xl border border-line bg-surface p-5 sm:grid-cols-2">
                  <Field label={pick("اسم الشركة", "Company name")} htmlFor="cn"><Input id="cn" value={f.company_name} onChange={(e) => setF({ ...f, company_name: e.target.value })} /></Field>
                  <Field label={pick("رأس المال المدفوع (ريال)", "Paid-up capital (SAR)")} htmlFor="cap" hint={pick("إن تركته فارغاً نحاول استخراجه من وثائقك", "Leave empty to read it from your documents")}>
                    <Input id="cap" inputMode="numeric" dir="ltr" placeholder="5,000,000" value={f.capital} onChange={(e) => setF({ ...f, capital: e.target.value })} />
                  </Field>
                  <Field label={pick("وصف نموذج العمل", "Business model")} htmlFor="desc" className="sm:col-span-2" hint={pick("مثل: الخدمة، العملاء المستهدفون، الشركاء، وهل لديكم مسؤول التزام", "e.g. the service, target customers, partners, whether you have a compliance officer")}>
                    <Textarea id="desc" rows={4} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
                  </Field>
                  <Field label={pick("حجم العمليات الشهري المتوقع (ريال)", "Expected monthly volume (SAR)")} htmlFor="vol">
                    <Input id="vol" inputMode="numeric" dir="ltr" value={f.volume} onChange={(e) => setF({ ...f, volume: e.target.value })} />
                  </Field>
                  <Field label={pick("موقع استضافة البيانات", "Data hosting location")} htmlFor="host">
                    <Select id="host" value={f.hosting} onChange={(e) => setF({ ...f, hosting: e.target.value })}>
                      <option value="">{pick("غير محدد", "Not specified")}</option>
                      <option value="السعودية">{pick("داخل المملكة", "Inside Saudi Arabia")}</option>
                      <option value="Abroad">{pick("خارج المملكة", "Outside Saudi Arabia")}</option>
                    </Select>
                  </Field>
                  <div className="sm:col-span-2"><Checkbox label={pick("نعتمد على مزودي خدمات خارجيين في وظائف جوهرية (سحابة، معالجة، تحقق هوية…)", "We rely on third parties for core functions (cloud, processing, identity…)")} checked={f.third} onChange={(v) => setF({ ...f, third: v })} /></div>
                </div>
              </li>

              <li>
                <h2 className="flex items-center gap-2 text-[17px] font-semibold"><span className="grid size-6 place-items-center rounded-full bg-primary text-[12px] text-white">3</span>{pick("وثائقك", "Your documents")}<span className="text-[13px] font-normal text-muted">({t.common.optional})</span></h2>
                <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
                  onDrop={(e) => { e.preventDefault(); setDrag(false); addFiles(e.dataTransfer.files); }}
                  className={cn("mt-4 grid place-items-center rounded-xl border-2 border-dashed bg-surface px-6 py-9 text-center transition-colors", drag ? "border-primary bg-primary-soft/40" : "border-line-strong")}>
                  <span className="grid size-11 place-items-center rounded-full bg-primary-soft text-primary"><Upload className="size-5" /></span>
                  <p className="mt-3 text-[14.5px] font-medium">{pick("اسحب الملفات هنا أو", "Drag files here or")} <button type="button" onClick={() => input.current?.click()} className="text-primary hover:underline">{pick("اختر من جهازك", "browse")}</button></p>
                  <p className="mt-1 text-[12.5px] text-muted">{pick("PDF أو DOCX أو TXT · حتى 10 ملفات · 8 ميجابايت للملف. نتحقق من أن كل ملف وثيقة حقيقية مقروءة ونطابق محتواها مع العناصر الأساسية المطلوبة لنوعها.", "PDF, DOCX or TXT · up to 10 files · 8 MB each. We verify each file is a real, readable document and check its content against the core elements its type requires.")}</p>
                  <input ref={input} type="file" multiple accept=".pdf,.docx,.txt" className="hidden" onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} />
                </div>
                {fileErr.length > 0 && <div className="mt-3"><Notice tone="danger"><ul className="flex flex-col gap-0.5">{fileErr.map((e) => <li key={e}>{e}</li>)}</ul></Notice></div>}
                {files.length > 0 && (
                  <ul className="mt-3 flex flex-col gap-2">
                    {files.map((x, i) => (
                      <li key={i} className="flex items-center gap-3 rounded-lg border border-line bg-surface px-3 py-2">
                        <FileText className="size-4 shrink-0 text-muted" />
                        <span className="ltr min-w-0 flex-1 truncate text-start text-[13px]">{x.file.name}</span>
                        <Select aria-label={pick("نوع الوثيقة", "Document type")} className="h-8 w-[200px] text-[12.5px]" value={x.type}
                          onChange={(e) => setFiles(files.map((y, j) => (j === i ? { ...y, type: e.target.value } : y)))}>
                          <option value="AUTO">{pick("تعرّف تلقائي", "Auto-detect")}</option>
                          {DOC_TYPES.map((d) => <option key={d} value={d}>{label("docType", d)}</option>)}
                        </Select>
                        <Button variant="ghost" size="icon-sm" aria-label={pick("إزالة", "Remove")} onClick={() => setFiles(files.filter((_, j) => j !== i))}><Trash2 /></Button>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            </ol>
            {err && <div className="mt-6"><Notice tone="danger">{err}</Notice></div>}
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Button size="lg" loading={busy} onClick={submit}>{busy ? pick("جارٍ التحليل…", "Analysing…") : pick("افحص الجاهزية", "Check readiness")}</Button>
              <p className="text-[12.5px] text-muted">{pick("تقييم أولي لدعم القرار وليس استشارة قانونية أو قراراً رسمياً. لا تُحفظ الملفات المرفوعة.", "Preliminary decision support — not legal advice or an official decision. Uploaded files are not stored.")}</p>
            </div>
          </div>
        ) : (
          <div className="animate-rise">
            <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
              <Button variant="ghost" size="sm" onClick={() => setRes(null)}><RotateCcw />{pick("فحص جديد أو تعديل البيانات", "New check or edit details")}</Button>
              <Button variant="secondary" size="sm" onClick={() => window.print()}><Printer />{pick("طباعة / حفظ PDF", "Print / save PDF")}</Button>
            </div>

            <section className="mt-4 grid gap-6 rounded-2xl border border-line bg-surface p-6 md:grid-cols-[auto_1fr] md:items-center md:p-8">
              <ScoreRing value={res.score} size={156} stroke={12} tone={lv!.color} track="#E9EEF5">
                <div><p className="ltr text-[38px] font-semibold leading-none">{res.score}<span className="text-[18px] text-muted">%</span></p>
                  <p className="mt-1 text-[12px] text-muted">{pick("نسبة الجاهزية", "Readiness")}</p></div>
              </ScoreRing>
              <div>
                <span className={cn("inline-flex rounded-full px-3 py-1 text-[13px] font-semibold", lv!.soft)}>{pick(lv!.ar, lv!.en)}</span>
                <h1 className="mt-3 text-[24px] font-semibold leading-snug">{res.company_name || pick("نتيجة الفحص", "Your result")}<span className="text-muted"> · {label("category", res.service_category)}</span></h1>
                {res.capital_used != null && <p className="mt-1 text-[13.5px] text-muted">{pick("رأس المال المعتمد في الفحص:", "Capital used in the check:")} <span className="ltr font-medium text-ink">{fmtNum(res.capital_used)}</span> {t.common.sar}</p>}
                <div className="mt-5 grid max-w-xl grid-cols-2 gap-2.5 sm:grid-cols-4">
                  {[{ n: res.counts.met, l: pick("مستوفى", "Met"), c: "text-success" }, { n: res.counts.gaps, l: pick("فجوات", "Gaps"), c: "text-danger" },
                    { n: res.counts.insufficient, l: pick("معلومات ناقصة", "Needs info"), c: "text-warning" }, { n: res.counts.risks, l: pick("مؤشرات مخاطر", "Risk indicators"), c: "text-warning" }].map((k) => (
                    <div key={k.l} className="rounded-xl border border-line px-3 py-3"><p className={cn("ltr text-[22px] font-semibold leading-none", k.c)}>{k.n}</p><p className="mt-1.5 text-[12px] text-muted">{k.l}</p></div>
                  ))}
                </div>
              </div>
            </section>

            <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
              <div className="flex flex-col gap-8">
                {res.documents.analysed.length > 0 && <DocChecks docs={res.documents.analysed} />}
                {res.consistency.length > 0 && (
                  <section>
                    <h2 className="flex items-center gap-2 text-[17px] font-semibold"><TriangleAlert className="size-5 text-warning" />{pick("ملاحظات اتساق البيانات", "Consistency issues")}</h2>
                    <ul className="mt-3 flex flex-col gap-2">
                      {res.consistency.map((c, i) => <li key={i} className="rounded-xl border border-[#f1e0bd] bg-warning-soft/50 px-4 py-3 text-[13.5px]">{pick(c.ar, c.en)}</li>)}
                    </ul>
                  </section>
                )}
                {res.next_steps.length > 0 && (
                  <section>
                    <h2 className="flex items-center gap-2 text-[17px] font-semibold"><ListChecks className="size-5 text-primary" />{pick("الخطوات التالية", "Next steps")}</h2>
                    <ol className="mt-3 flex flex-col gap-2 rounded-xl border border-line bg-surface p-4">
                      {res.next_steps.map((s, i) => (
                        <li key={i} className="flex gap-3 text-[13.5px] leading-relaxed"><span className="ltr grid size-6 shrink-0 place-items-center rounded-full bg-primary-soft text-[12px] font-semibold text-primary">{i + 1}</span>{s}</li>
                      ))}
                    </ol>
                  </section>
                )}
                {gaps.length > 0 && (
                  <section>
                    <h2 className="text-[17px] font-semibold">{pick("ما يلزم معالجته", "What needs attention")} <span className="text-muted">({gaps.length})</span></h2>
                    <ul className="mt-3 flex flex-col gap-2.5">{gaps.map((r) => <ReqRow key={r.code} r={r} />)}</ul>
                  </section>
                )}
                {res.risks.length > 0 && (
                  <section>
                    <h2 className="flex items-center gap-2 text-[17px] font-semibold"><ShieldAlert className="size-5 text-warning" />{pick("مؤشرات المخاطر", "Risk indicators")}</h2>
                    <ul className="mt-3 flex flex-col gap-2">
                      {res.risks.map((r) => (
                        <li key={r.code} className="flex items-start gap-3 rounded-xl border border-[#f1e0bd] bg-warning-soft/50 px-4 py-3 text-[13.5px]">
                          <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warning" /><span>{pick(r.title_ar, r.title_en)}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
                {met.length > 0 && (
                  <section>
                    <h2 className="text-[17px] font-semibold">{pick("متطلبات مستوفاة", "Requirements met")} <span className="text-muted">({met.length})</span></h2>
                    <ul className="mt-3 flex flex-col gap-2.5">{met.map((r) => <ReqRow key={r.code} r={r} />)}</ul>
                  </section>
                )}
              </div>

              <aside className="flex flex-col gap-6">
                {res.key_rules.length > 0 && (
                  <section className="rounded-xl border border-line bg-surface p-4">
                    <h3 className="text-[14.5px] font-semibold">{pick("قواعد أساسية لنشاطك", "Key rules for your activity")}</h3>
                    <ul className="mt-3 flex flex-col gap-3">
                      {res.key_rules.map((k, i) => (
                        <li key={i} className="text-[13px] leading-relaxed">
                          <p>{pick(k.text_ar, k.text_en)}</p>
                          {k.evidence && (
                            <a href={k.evidence.source_url} target="_blank" rel="noopener noreferrer" className="mt-0.5 inline-flex items-center gap-1 text-[12px] text-primary hover:underline">
                              <ExternalLink className="size-3" />{pick(k.evidence.title_ar, k.evidence.title_en)} · {k.evidence.section.split(" - ")[0]}
                            </a>
                          )}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
                <section className="rounded-xl border border-line bg-surface p-4">
                  <h3 className="text-[14.5px] font-semibold">{pick("الوثائق المطلوبة", "Required documents")}</h3>
                  {res.documents.analysed.length === 0 && <p className="mt-2 text-[12.5px] text-muted">{pick("لم تُرفع وثائق. ارفعها لرفع دقة الفحص.", "No documents uploaded. Add them for a more accurate check.")}</p>}
                  {res.documents.present.length > 0 && (
                    <ul className="mt-3 flex flex-col gap-1">
                      {res.documents.present.map((m) => <li key={m} className="flex items-center gap-2 text-[12.5px] text-ink-2"><Check className="size-3.5 text-success" />{label("docType", m)}</li>)}
                    </ul>
                  )}
                  {res.documents.missing.length > 0 && (
                    <div className="mt-4 border-t border-line pt-3">
                      <p className="text-[12.5px] font-medium text-ink-2">{pick("وثائق مطلوبة لم تُرفق", "Required but not provided")}</p>
                      <ul className="mt-1.5 flex flex-col gap-1">
                        {res.documents.missing.map((m) => <li key={m} className="flex items-center gap-2 text-[12.5px] text-ink-2"><X className="size-3.5 text-danger" />{label("docType", m)}</li>)}
                      </ul>
                    </div>
                  )}
                </section>
                <p className="text-[12px] leading-relaxed text-muted">{pick(res.notice_ar, res.notice_en)}</p>
              </aside>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
