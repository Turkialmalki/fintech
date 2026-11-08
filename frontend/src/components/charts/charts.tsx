"use client";

import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
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

/** Donut with the total in the middle and a legend; accessible as a labelled image. */
export function Donut({ parts, size = 168, centerLabel }: { parts: { label: string; value: number; color: string }[]; size?: number; centerLabel?: string }) {
  const { fmtNum } = useI18n();
  const total = parts.reduce((s, p) => s + p.value, 0);
  const shown = parts.filter((p) => p.value > 0);
  return (
    <div className="flex flex-wrap items-center gap-5">
      <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={parts.map((p) => `${p.label}: ${p.value}`).join(", ")}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={shown.length ? shown : [{ label: "", value: 1, color: "#E9EEF5" }]} dataKey="value" nameKey="label" innerRadius="68%" outerRadius="100%"
              paddingAngle={shown.length > 1 ? 2 : 0} stroke="none" isAnimationActive={false} startAngle={90} endAngle={-270}>
              {(shown.length ? shown : [{ color: "#E9EEF5" }]).map((p, i) => <Cell key={i} fill={p.color} />)}
            </Pie>
            {shown.length > 0 && <Tooltip content={<PieTip />} />}
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
          <div><p className="text-[24px] font-semibold leading-none num">{fmtNum(total)}</p>{centerLabel && <p className="mt-1 text-[11.5px] text-muted">{centerLabel}</p>}</div>
        </div>
      </div>
      <ul className="flex min-w-[150px] flex-1 flex-col gap-1.5">
        {parts.map((p) => (
          <li key={p.label} className="flex items-center justify-between gap-3 text-[12.5px]">
            <span className="flex items-center gap-2 text-ink-2"><span className="size-2.5 rounded-sm" style={{ background: p.color }} />{p.label}</span>
            <span className="flex items-center gap-2 num"><span className="font-semibold text-ink">{fmtNum(p.value)}</span>{total ? <span className="w-9 text-end text-[11.5px] text-faint">{Math.round((p.value / total) * 100)}٪</span> : null}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PieTip({ active, payload }: { active?: boolean; payload?: { name?: string; value: number }[] }) {
  const { fmtNum } = useI18n();
  if (!active || !payload?.length) return null;
  return <div className="rounded-md border border-line bg-surface px-3 py-2 text-[12.5px] shadow-pop"><p className="text-muted">{payload[0].name}</p><p className="font-medium num">{fmtNum(payload[0].value)}</p></div>;
}

/** Grouped vertical bars over time (RTL-aware). */
export function GroupedBars({ data, x, series, height = 230 }: {
  data: Record<string, unknown>[]; x: string; series: { key: string; label: string; color: string }[]; height?: number;
}) {
  const { dir, fmtNum } = useI18n();
  const rtl = dir === "rtl";
  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 8, right: rtl ? 0 : 8, left: rtl ? 8 : 0, bottom: 0 }} barGap={3}>
          <CartesianGrid stroke="#E5EAF0" vertical={false} />
          <XAxis dataKey={x} reversed={rtl} tick={AXIS} tickLine={false} axisLine={{ stroke: "#E5EAF0" }} />
          <YAxis orientation={rtl ? "right" : "left"} tick={AXIS} tickLine={false} axisLine={false} width={30} allowDecimals={false} tickFormatter={(v) => fmtNum(v)} />
          <Tooltip content={<MultiTip series={series} />} cursor={{ fill: "#F1F4F8" }} />
          {series.map((s) => <Bar key={s.key} dataKey={s.key} fill={s.color} radius={[4, 4, 0, 0]} maxBarSize={18} isAnimationActive={false} />)}
        </BarChart>
      </ResponsiveContainer>
      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-[12.5px] text-ink-2">
        {series.map((s) => <li key={s.key} className="flex items-center gap-2"><span className="size-2.5 rounded-sm" style={{ background: s.color }} />{s.label}</li>)}
      </ul>
    </div>
  );
}

function MultiTip({ active, payload, label, series }: { active?: boolean; payload?: { dataKey: string; value: number; color: string }[]; label?: string; series: { key: string; label: string }[] }) {
  const { fmtNum } = useI18n();
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-line bg-surface px-3 py-2 text-[12.5px] shadow-pop">
      <p className="mb-1 text-muted">{label}</p>
      {payload.map((p) => <p key={p.dataKey} className="flex items-center gap-2"><span className="size-2 rounded-sm" style={{ background: p.color }} />{series.find((s) => s.key === p.dataKey)?.label}: <span className="font-medium num">{fmtNum(p.value)}</span></p>)}
    </div>
  );
}

/** Percentage bars with a colour scale (green ≥ 80, amber ≥ 60, red below). */
export function PercentBars({ data }: { data: { label: string; value: number }[] }) {
  const tone = (v: number) => (v >= 80 ? "#15966A" : v >= 60 ? "#D99024" : "#D94B52");
  return (
    <ul className="flex flex-col gap-3.5">
      {data.map((d) => (
        <li key={d.label} className="text-[12.5px]">
          <div className="mb-1.5 flex justify-between gap-3"><span className="truncate text-ink-2">{d.label}</span><span className="font-semibold num" style={{ color: tone(d.value) }}>{d.value}%</span></div>
          <div className="h-2 overflow-hidden rounded-full bg-surface-2"><div className="h-full rounded-full" style={{ width: `${d.value}%`, background: tone(d.value) }} /></div>
        </li>
      ))}
    </ul>
  );
}
