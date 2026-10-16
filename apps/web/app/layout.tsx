import type { JSX, ReactNode } from "react";

import "../styles/tokens.css";

export const metadata = {
  title: "PartsIQ — synthetic demo",
  description: "AI-assisted spare-parts identification. Independent synthetic demonstration project.",
};

// Base responsive shell (locale/theme wiring is layered by F06/F07/F08). The lang/dir
// default to English LTR here; the locale switcher updates them.
export default function RootLayout({ children }: { children: ReactNode }): JSX.Element {
  return (
    <html lang="en" dir="ltr">
      <body>
        <div style={{ maxWidth: 960, margin: "0 auto", padding: "16px" }}>{children}</div>
      </body>
    </html>
  );
}
