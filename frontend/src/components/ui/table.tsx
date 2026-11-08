"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { Button } from "./button";

export function Table({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("overflow-x-auto scroll-thin", className)}>
      <table className="w-full border-collapse text-[13.5px]">{children}</table>
    </div>
  );
}

export function Th({ children, className, ...p }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return <th scope="col" className={cn("whitespace-nowrap border-b border-line bg-canvas/70 px-4 py-2.5 text-start text-[12.5px] font-medium text-muted first:ps-5 last:pe-5", className)} {...p}>{children}</th>;
}

export function Td({ children, className, ...p }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("border-b border-line px-4 py-3 align-middle first:ps-5 last:pe-5", className)} {...p}>{children}</td>;
}

export function Tr({ children, className, onClick, ...p }: React.HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr onClick={onClick} className={cn("transition-colors", onClick && "cursor-pointer hover:bg-canvas", className)}
      tabIndex={onClick ? 0 : undefined} onKeyDown={onClick ? (e) => { if (e.key === "Enter") onClick(e as never); } : undefined} {...p}>
      {children}
    </tr>
  );
}

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const { t, dir, fmtNum } = useI18n();
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const Prev = dir === "rtl" ? ChevronRight : ChevronLeft;
  const Next = dir === "rtl" ? ChevronLeft : ChevronRight;
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <nav aria-label="pagination" className="flex items-center justify-between gap-3 px-5 py-3 text-[13px] text-muted">
      <span className="num">{fmtNum(from)}–{fmtNum(to)} {t.common.of} {fmtNum(total)}</span>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="icon-sm" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label={t.common.previous}><Prev /></Button>
        <span className="px-2 num">{fmtNum(page)} / {fmtNum(pages)}</span>
        <Button variant="ghost" size="icon-sm" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label={t.common.next}><Next /></Button>
      </div>
    </nav>
  );
}
