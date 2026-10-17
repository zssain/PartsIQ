import { cookies } from "next/headers";
import type { JSX, ReactNode } from "react";

import "../styles/tokens.css";
import { requestLocale } from "@/i18n/request";
import { Aurora } from "@/components/ui/Aurora";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { SiteFooter } from "@/components/layout/SiteFooter";

export const metadata = {
  title: "PartsIQ — AI spare-parts identification (synthetic demo)",
  description:
    "AI-assisted spare-parts identification for equipment distributors. Independent synthetic demonstration.",
};

// Root shell. F07 lang/dir from the locale cookie; F08 no-flash theme script; the oil-slick aurora,
// sticky glass header and footer frame every page.
export default async function RootLayout({ children }: { children: ReactNode }): Promise<JSX.Element> {
  const store = await cookies();
  const { locale, direction } = requestLocale(store.get("locale")?.value ?? null);
  const themeInit =
    "try{var t=localStorage.getItem('pq-theme');" +
    "if(t!=='light'&&t!=='dark'){t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}" +
    "document.documentElement.setAttribute('data-theme',t);}catch(e){}";
  return (
    // suppressHydrationWarning: the no-flash script below sets data-theme on <html> before React
    // hydrates, so the server (no attribute) and client (data-theme) differ by design — scope the
    // suppression to this element only.
    <html lang={locale} dir={direction} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body>
        <Aurora />
        <SiteHeader locale={locale} />
        <main style={{ minHeight: "70vh" }}>{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
