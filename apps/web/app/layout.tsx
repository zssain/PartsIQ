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
  return (
    <html lang={locale} dir={direction}>
      <body>
        <div style={{ maxWidth: 960, margin: "0 auto", padding: "16px" }}>{children}</div>
      </body>
    </html>
  );
}
