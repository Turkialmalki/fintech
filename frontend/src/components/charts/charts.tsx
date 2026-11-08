"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useI18n } from "@/lib/i18n";

const AXIS = { fontSize: 11.5, fill: "#68778B" };

function Tip({ active, payload, label, unit }: { active?: boolean; payload?: { value: number; name?: string; color?: string }[]; label?: string; unit?: string }) {
  const { fmtNum } = useI18n();
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2 text-[12.5px] shadow-pop">
      {label && <p className="mb-0.5 text-muted">{label}</p>}
      {payload.map((p, i) => <p key={i} className="font-medium num">{fmtNum(p.value)}{unit ? ` ${unit}` : ""}</p>)}
    </div>
  );
}

/** RTL-aware: the time axis runs right-to-left in Arabic and the value axis sits on the right. */
export function TrendLine({ data, x, y, height = 220, color = "#2457D6", unit }: {
  data: Record<string, unknown>[]; x: string; y: string; height?: number; color?: string; unit?: string;
}) {
  const { dir, fmtNum } = useI18n();
  const rtl = dir === "rtl";
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: rtl ? 0 : 8, left: rtl ? 8 : 0, bottom: 0 }}>
        <CartesianGrid stroke="#E5EAF0" vertical={false} />
        <XAxis dataKey={x} reversed={rtl} tick={AXIS} tickLine={false} axisLine={{ stroke: "#E5EAF0" }} minTickGap={24} />
        <YAxis orientation={rtl ? "right" : "left"} tick={AXIS} tickLine={false} axisLine={false} width={36} allowDecimals={false} tickFormatter={(v) => fmtNum(v)} />
        <Tooltip content={<Tip unit={unit} />} cursor={{ stroke: "#D3DBE6" }} />
        <Line type="monotone" dataKey={y} stroke={color} strokeWidth={2} dot={{ r: 2.5, fill: color }} activeDot={{ r: 4 }} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Horizontal bars as plain CSS: inherits document direction, never overlaps labels. */
export function HBars({ data }: { data: { label: string; value: number; color?: string }[]; height?: number }) {
  const { fmtNum } = useI18n();
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <ul className="flex flex-col gap-3">
      {data.map((d) => (
        <li key={d.label} className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)_2.5rem] items-center gap-3 text-[12.5px]">
          <span className="truncate text-ink-2" title={d.label}>{d.label}</span>
          <span className="h-2.5 overflow-hidden rounded-full bg-surface-2">
            <span className="block h-full rounded-full" style={{ width: `${(d.value / max) * 100}%`, background: d.color ?? "#2457D6" }} />
          </span>
          <span className="text-end font-medium num">{fmtNum(d.value)}</span>
        </li>
      ))}
    </ul>
  );
}

/** Proportional stacked strip — compact distribution without a pie chart. */
export function Strip({ parts }: { parts: { label: string; value: number; color: string }[] }) {
  const { fmtNum } = useI18n();
  const total = parts.reduce((s, p) => s + p.value, 0) || 1;
  return (
    <div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-surface-2" role="img" aria-label={parts.map((p) => `${p.label}: ${p.value}`).join(", ")}>
        {parts.filter((p) => p.value > 0).map((p) => <span key={p.label} style={{ width: `${(p.value / total) * 100}%`, background: p.color }} className="h-full first:rounded-s-full last:rounded-e-full" />)}
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1.5">
        {parts.map((p) => (
          <li key={p.label} className="flex items-center justify-between gap-2 text-[12.5px]">
            <span className="flex items-center gap-2 text-ink-2"><span className="size-2 rounded-full" style={{ background: p.color }} />{p.label}</span>
            <span className="font-medium num">{fmtNum(p.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
