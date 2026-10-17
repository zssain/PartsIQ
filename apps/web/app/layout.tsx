import { cookies } from "next/headers";
import type { JSX, ReactNode } from "react";

import "../styles/tokens.css";
import { requestLocale } from "@/i18n/request";

export const metadata = {
  title: "PartsIQ — synthetic demo",
  description: "AI-assisted spare-parts identification. Independent synthetic demonstration project.",
};

// Root shell. F07: lang/dir come from the `locale` preference cookie (default English LTR).
// Theme (F08) and the responsive shell (F06) are layered below.
export default async function RootLayout({ children }: { children: ReactNode }): Promise<JSX.Element> {
  const store = await cookies();
  const { locale, direction } = requestLocale(store.get("locale")?.value ?? null);
  // F08: set data-theme before paint from saved preference then system setting. This touches a
  // DOM attribute React does not manage, so there is no hydration mismatch and no flash.
  const themeInit =
    "try{var t=localStorage.getItem('pq-theme');" +
    "if(t!=='light'&&t!=='dark'){t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}" +
    "document.documentElement.setAttribute('data-theme',t);}catch(e){}";
  return (
    <html lang={locale} dir={direction}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body>
        <div style={{ maxWidth: 960, margin: "0 auto", padding: "16px" }}>{children}</div>
      </body>
    </html>
  );
}
