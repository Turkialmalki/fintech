import { ChevronDown } from "lucide-react";
import { forwardRef, useId } from "react";
import { cn } from "@/lib/utils";

const base =
  "w-full rounded-md border border-line-strong bg-surface text-ink placeholder:text-faint transition-colors " +
  "hover:border-[#c4cedb] focus:outline-none focus:border-primary focus:ring-[3px] focus:ring-primary/15 disabled:bg-surface-2 disabled:text-muted " +
  "aria-[invalid=true]:border-danger-base aria-[invalid=true]:ring-danger-base/15";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => (
  <input ref={ref} className={cn(base, "h-9 px-3 text-[13.5px]", className)} {...p} />
));
Input.displayName = "Input";

export const Textarea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, ref) => (
  <textarea ref={ref} className={cn(base, "px-3 py-2 text-[13.5px] min-h-[88px] leading-relaxed", className)} {...p} />
));
Textarea.displayName = "Textarea";

export const Select = forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(({ className, children, ...p }, ref) => (
  <div className="relative">
    <select ref={ref} className={cn(base, "h-9 appearance-none ps-3 pe-9 text-[13.5px]", className)} {...p}>{children}</select>
    <ChevronDown className="pointer-events-none absolute end-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
  </div>
));
Select.displayName = "Select";

export function Field({ label, hint, error, required, children, className, htmlFor }: {
  label: string; hint?: string; error?: string; required?: boolean; children: React.ReactNode; className?: string; htmlFor?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={htmlFor} className="text-[13px] font-medium text-ink-2">
        {label}{required && <span className="text-danger ms-0.5" aria-hidden>*</span>}
      </label>
      {children}
      {error ? <p role="alert" className="text-[12px] text-danger">{error}</p> : hint ? <p className="text-[12px] text-muted">{hint}</p> : null}
    </div>
  );
}

export function Checkbox({ label, checked, onChange, id }: { label: React.ReactNode; checked: boolean; onChange: (v: boolean) => void; id?: string }) {
  const auto = useId();
  const cid = id ?? auto;
  return (
    <label htmlFor={cid} className="flex items-start gap-2.5 text-[13.5px] text-ink-2 cursor-pointer">
      <input id={cid} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)}
        className="mt-1 size-4 rounded border-line-strong accent-primary" />
      <span>{label}</span>
    </label>
  );
}

export function Segmented<T extends string>({ value, onChange, options, size = "md", ariaLabel }: {
  value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; size?: "sm" | "md"; ariaLabel?: string;
}) {
  return (
    <div role="radiogroup" aria-label={ariaLabel} className="inline-flex rounded-md bg-surface-2 p-0.5 border border-line">
      {options.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={value === o.value} onClick={() => onChange(o.value)}
          className={cn("rounded-[5px] font-medium transition-colors", size === "sm" ? "px-2.5 h-7 text-[12.5px]" : "px-3 h-8 text-[13px]",
            value === o.value ? "bg-surface text-ink shadow-[0_1px_2px_rgb(20_34_56/0.08)]" : "text-muted hover:text-ink")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}
