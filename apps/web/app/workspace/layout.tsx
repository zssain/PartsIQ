import { cookies } from "next/headers";
import type { JSX, ReactNode } from "react";

import "../../styles/app.css";
import { WorkspaceProviders } from "@/components/app/WorkspaceProviders";

export const metadata = {
  title: "PartsIQ workspace",
  description: "Spare-parts enquiries with compatibility checks, specialist collaboration and human approval (synthetic demo data).",
};

// One shell for every workspace screen (customer, reviewer, administrator). The locale cookie is
// read on the server so <html lang/dir> and the shell strings agree on first paint.
export default async function WorkspaceLayout({ children }: { children: ReactNode }): Promise<JSX.Element> {
  const store = await cookies();
  const locale = store.get("locale")?.value === "ar" ? "ar" : "en";
  return <WorkspaceProviders locale={locale}>{children}</WorkspaceProviders>;
}
