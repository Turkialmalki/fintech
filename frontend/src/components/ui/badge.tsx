import { cn } from "@/lib/utils";

const tones = {
  neutral: "bg-surface-2 text-ink-2 border-line",
  primary: "bg-primary-soft text-primary border-[#d3e0fa]",
  success: "bg-success-soft text-success border-[#cce9dd]",
  warning: "bg-warning-soft text-warning border-[#f1e0bd]",
  danger: "bg-danger-soft text-danger border-[#f5d3d5]",
  critical: "bg-danger-base text-white border-danger-base",
  accent: "bg-accent-soft text-[#4b5fd0] border-[#dde1fb]",
} as const;

export type Tone = keyof typeof tones;

export function Badge({ tone = "neutral", dot, className, children }: { tone?: Tone; dot?: boolean; className?: string; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-px text-[12px] font-medium leading-5", tones[tone], className)}>
      {dot && <span className="size-1.5 rounded-full bg-current opacity-80" aria-hidden />}
      {children}
    </span>
  );
}

/** Severity as a short bar meter — conveys order without relying on colour alone. */
export function SeverityMark({ severity, label }: { severity: string; label: string }) {
  const level = { INFO: 0, LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 }[severity] ?? 0;
  const color = { INFO: "bg-accent", LOW: "bg-success", MEDIUM: "bg-warning-base", HIGH: "bg-danger-base", CRITICAL: "bg-danger" }[severity] ?? "bg-faint";
  return (
    <span className="inline-flex items-center gap-2 text-[12.5px] font-medium text-ink-2">
      <span className="inline-flex items-end gap-[2px]" aria-hidden>
        {[0, 1, 2, 3].map((i) => (
          <span key={i} className={cn("w-[3px] rounded-full", i < Math.max(level, 1) ? color : "bg-line-strong")} style={{ height: 6 + i * 3 }} />
        ))}
      </span>
      {label}
    </span>
  );
}
