"use client";

import * as D from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { Button } from "./button";

export function Dialog({ open, onOpenChange, title, description, children, footer, size = "md" }: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; description?: string; children?: React.ReactNode; footer?: React.ReactNode;
  size?: "sm" | "md" | "lg";
}) {
  const { t } = useI18n();
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-50 bg-[#142238]/30 backdrop-blur-[2px] data-[state=open]:animate-[rise_.2s_ease-out]" />
        <D.Content className={cn("fixed start-1/2 top-[12vh] z-50 w-[calc(100vw-2rem)] -translate-x-1/2 rtl:translate-x-1/2 rounded-xl bg-surface shadow-pop border border-line",
          "max-h-[80vh] flex flex-col focus:outline-none", { sm: "max-w-md", md: "max-w-xl", lg: "max-w-3xl" }[size])}>
          <div className="flex items-start justify-between gap-4 px-6 pt-5 pb-3">
            <div>
              <D.Title className="text-[17px] font-semibold text-ink">{title}</D.Title>
              {description && <D.Description className="mt-1 text-[13px] text-muted">{description}</D.Description>}
            </div>
            <D.Close asChild><Button variant="ghost" size="icon-sm" aria-label={t.common.close}><X /></Button></D.Close>
          </div>
          <div className="overflow-y-auto scroll-thin px-6 pb-4">{children}</div>
          {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-6 py-3.5 bg-canvas/60 rounded-b-xl">{footer}</div>}
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}

export function Drawer({ open, onOpenChange, title, subtitle, children, width = "max-w-2xl" }: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; subtitle?: React.ReactNode; children: React.ReactNode; width?: string;
}) {
  const { t } = useI18n();
  return (
    <D.Root open={open} onOpenChange={onOpenChange}>
      <D.Portal>
        <D.Overlay className="fixed inset-0 z-50 bg-[#142238]/25" />
        <D.Content className={cn("fixed inset-y-0 end-0 z-50 flex w-full flex-col bg-surface shadow-pop border-s border-line focus:outline-none", width)}>
          <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-4">
            <div className="min-w-0">
              <D.Title className="text-[16px] font-semibold text-ink">{title}</D.Title>
              {subtitle && <D.Description asChild><div className="mt-1 text-[13px] text-muted">{subtitle}</div></D.Description>}
            </div>
            <D.Close asChild><Button variant="ghost" size="icon-sm" aria-label={t.common.close}><X /></Button></D.Close>
          </div>
          <div className="flex-1 overflow-y-auto scroll-thin px-6 py-5">{children}</div>
        </D.Content>
      </D.Portal>
    </D.Root>
  );
}

/** Confirmation for consequential actions; optional explicit acknowledgement checkbox. */
export function ConfirmDialog({ open, onOpenChange, title, description, confirmLabel, tone = "primary", onConfirm, acknowledge, children }: {
  open: boolean; onOpenChange: (o: boolean) => void; title: string; description?: string; confirmLabel: string; tone?: "primary" | "danger";
  onConfirm: () => Promise<unknown> | void; acknowledge?: string; children?: React.ReactNode;
}) {
  const { t } = useI18n();
  const [ack, setAck] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) setAck(false); onOpenChange(o); }} title={title} description={description} size="sm"
      footer={<>
        <Button variant="secondary" onClick={() => onOpenChange(false)}>{t.common.cancel}</Button>
        <Button variant={tone === "danger" ? "danger" : "primary"} loading={busy} disabled={!!acknowledge && !ack}
          onClick={async () => { setBusy(true); try { await onConfirm(); onOpenChange(false); setAck(false); } finally { setBusy(false); } }}>
          {confirmLabel}
        </Button>
      </>}>
      {children}
      {acknowledge && (
        <label className="mt-2 flex items-start gap-2.5 rounded-lg border border-line bg-canvas p-3 text-[13px] text-ink-2 cursor-pointer">
          <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-1 size-4 accent-primary" />
          {acknowledge}
        </label>
      )}
    </Dialog>
  );
}
