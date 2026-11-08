"use client";

import { Badge, SeverityMark } from "@/components/ui/badge";
import { useI18n } from "@/lib/i18n";
import { STATUS_TONE } from "@/lib/utils";

export function StatusBadge({ status, group = "status" }: { status: string; group?: "status" | "draftStatus" | "runStatus" }) {
  const { label } = useI18n();
  return <Badge tone={STATUS_TONE[status] ?? "neutral"} dot>{label(group, status)}</Badge>;
}

export function Severity({ value }: { value: string }) {
  const { label } = useI18n();
  return <SeverityMark severity={value} label={label("severity", value)} />;
}

export function RiskBadge({ value }: { value: string | null | undefined }) {
  const { label } = useI18n();
  if (!value) return <span className="text-faint">—</span>;
  const tone = ({ CRITICAL: "critical", HIGH: "danger", MEDIUM: "warning", LOW: "success" } as const)[value as "HIGH"] ?? "neutral";
  return <Badge tone={tone}>{label("severity", value)}</Badge>;
}

export function SyntheticTag() {
  const { t } = useI18n();
  return <Badge tone="warning">{t.demo.synthetic}</Badge>;
}

export function MockTag({ show = true }: { show?: boolean }) {
  const { t } = useI18n();
  if (!show) return null;
  return <span title={t.demo.mockHint}><Badge tone="warning">{t.demo.mock}</Badge></span>;
}

export function OriginTag({ origin }: { origin: string }) {
  const { t } = useI18n();
  const map: Record<string, [string, "accent" | "neutral" | "primary"]> = {
    AI: [t.assess.aiGenerated, "accent"], RULE: [t.assess.ruleBased, "neutral"], HUMAN: [t.assess.human, "primary"], MIXED: [t.assess.mixed, "primary"],
  };
  const [text, tone] = map[origin] ?? [origin, "neutral"];
  return <Badge tone={tone}>{text}</Badge>;
}
