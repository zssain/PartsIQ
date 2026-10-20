"use client";

import type { JSX, ReactNode } from "react";

import { AppLocaleProvider, type AppLocale } from "@/lib/app-i18n";
import { SessionProvider } from "@/lib/session";

import { AppShell } from "./AppShell";

export function WorkspaceProviders({ locale, children }: { locale: AppLocale; children: ReactNode }): JSX.Element {
  return (
    <AppLocaleProvider locale={locale}>
      <SessionProvider>
        <AppShell>{children}</AppShell>
      </SessionProvider>
    </AppLocaleProvider>
  );
}
