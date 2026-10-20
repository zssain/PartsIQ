import { cookies } from "next/headers";
import type { JSX, ReactNode } from "react";

import "../../styles/app.css";
import { AppLocaleProvider } from "@/lib/app-i18n";

// The login screen sits outside the workspace shell, so it reads the same `locale` cookie on the
// server (deterministic SSR, same source as <html lang/dir>) and provides the workspace strings.
export default async function LoginLayout({ children }: { children: ReactNode }): Promise<JSX.Element> {
  const store = await cookies();
  const locale = store.get("locale")?.value === "ar" ? "ar" : "en";
  return <AppLocaleProvider locale={locale}>{children}</AppLocaleProvider>;
}
