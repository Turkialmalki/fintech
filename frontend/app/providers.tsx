"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Toaster } from "sonner";
import { ApiError } from "@/lib/api";
import { I18nProvider, type Locale, useI18n } from "@/lib/i18n";

function ThemedToaster() {
  const { dir } = useI18n();
  return <Toaster dir={dir} position={dir === "rtl" ? "bottom-left" : "bottom-right"} richColors={false} closeButton
    toastOptions={{ className: "!font-[inherit] !rounded-lg !border-line !text-[13.5px]" }} />;
}

export function Providers({ locale, children }: { locale: Locale; children: React.ReactNode }) {
  const [qc] = useState(() => new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000, refetchOnWindowFocus: false,
        retry: (n, e) => !(e instanceof ApiError && [401, 403, 404, 422].includes(e.status)) && n < 2,
      },
    },
  }));
  return (
    <I18nProvider initial={locale}>
      <QueryClientProvider client={qc}>
        {children}
        <ThemedToaster />
      </QueryClientProvider>
    </I18nProvider>
  );
}
