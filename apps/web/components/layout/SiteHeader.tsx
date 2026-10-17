import { type JSX } from "react";

import { BrandLogo } from "@/components/BrandLogo";
import { ThemeControl } from "@/components/ui/ThemeControl";
import { LocaleControl } from "@/components/ui/LocaleControl";
import type { Locale } from "@/lib/features/f07_arabic_and_english_interface";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/architecture", label: "Architecture" },
  { href: "/demo", label: "Live demo" },
  { href: "/staff/inbox", label: "Staff" },
];

// Sticky glass site header: brand, primary nav, theme + locale controls.
export function SiteHeader({ locale = "en" }: { locale?: Locale }): JSX.Element {
  return (
    <header
      className="pq-glass"
      style={{
        position: "sticky", top: 0, zIndex: 50,
        borderBottom: "1px solid var(--pq-glass-border)",
      }}
    >
      <div
        className="pq-container"
        style={{ display: "flex", alignItems: "center", gap: 16, height: 64, justifyContent: "space-between" }}
      >
        <a href="/" aria-label="PartsIQ home" style={{ display: "flex", alignItems: "center" }}>
          <BrandLogo />
        </a>
        <nav aria-label="Primary" style={{ display: "flex", gap: 6, alignItems: "center" }} className="pq-nav">
          {LINKS.map((l) => (
            <a key={l.href} href={l.href} className="pq-chip" style={{ border: "none", color: "var(--pq-muted)" }}>
              {l.label}
            </a>
          ))}
        </nav>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <LocaleControl initial={locale} />
          <ThemeControl />
        </div>
      </div>
    </header>
  );
}
