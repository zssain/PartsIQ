import type { JSX, ReactNode } from "react";

import "../../styles/app.css";

export default function LoginLayout({ children }: { children: ReactNode }): JSX.Element {
  return <>{children}</>;
}
