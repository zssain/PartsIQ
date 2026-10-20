"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type JSX } from "react";
import { ArrowUpRight } from "lucide-react";
import { BrandLogo } from "@/components/BrandLogo";
import { ThemeControl } from "@/components/ui/ThemeControl";
import { LocaleControl } from "@/components/ui/LocaleControl";
import type { Locale } from "@/lib/features/f07_arabic_and_english_interface";
// "Workspace" and "Try demo" both lead to the current application (/workspace); the scripted
// scenarios are a secondary area. Sign in is for invited accounts.
const LINKS = [{href:"/",label:"Overview"},{href:"/workspace",label:"Workspace"},{href:"/demo/scenarios",label:"Guided scenarios"},{href:"/architecture",label:"How it works"},{href:"/login",label:"Sign in"}];
export function SiteHeader({ locale = "en" }: { locale?: Locale }): JSX.Element | null {
  const path = usePathname();
  if (path.startsWith("/workspace") || path.startsWith("/login")) return null;
  return <header className="pq-site-header"><a className="pq-skip-link" href="#main-content">Skip to content</a><div className="pq-container pq-header-inner"><Link href="/" aria-label="PartsIQ home"><BrandLogo /></Link><nav aria-label="Primary" className="pq-primary-nav">{LINKS.map(l => <a key={l.href} href={l.href} aria-current={path === l.href ? "page" : undefined}>{l.label}</a>)}</nav><div className="pq-header-controls"><LocaleControl initial={locale} /><ThemeControl /><Link href="/demo" className="pq-btn pq-btn-primary pq-header-cta">Try demo <ArrowUpRight size={15} /></Link></div></div></header>;
}
