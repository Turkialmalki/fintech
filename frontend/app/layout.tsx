import type { Metadata } from "next";
import { cookies } from "next/headers";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "منظومة الرصد التنظيمي الذكي", template: "%s · RIP" },
  description: "Saudi fintech regulatory readiness: check your business model against SAMA, SDAIA and AML requirements, with every requirement linked to its official source.",
  robots: { index: false, follow: false },
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Arabic is the default; the persisted preference is applied on the server so the first paint has the right direction.
  const locale = (await cookies()).get("rip_locale")?.value === "en" ? "en" : "ar";
  return (
    <html lang={locale} dir={locale === "ar" ? "rtl" : "ltr"} suppressHydrationWarning>
      <body>
        <Providers locale={locale}>{children}</Providers>
      </body>
    </html>
  );
}
