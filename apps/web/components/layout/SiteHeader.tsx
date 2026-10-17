"use client";
import { usePathname } from "next/navigation";
import { type JSX } from "react";
import { ArrowUpRight } from "lucide-react";
import { BrandLogo } from "@/components/BrandLogo";
import { ThemeControl } from "@/components/ui/ThemeControl";
import { LocaleControl } from "@/components/ui/LocaleControl";
import type { Locale } from "@/lib/features/f07_arabic_and_english_interface";
const LINKS = [{href:"/",label:"Overview"},{href:"/demo",label:"Workspace"},{href:"/architecture",label:"How it works"},{href:"/staff/inbox",label:"Staff inbox"}];
export function SiteHeader({ locale = "en" }: { locale?: Locale }): JSX.Element {
  const path = usePathname();
  return <header className="pq-site-header"><a className="pq-skip-link" href="#main-content">Skip to content</a><div className="pq-container pq-header-inner"><a href="/" aria-label="PartsIQ home"><BrandLogo /></a><nav aria-label="Primary" className="pq-primary-nav">{LINKS.map(l => <a key={l.href} href={l.href} aria-current={path === l.href ? "page" : undefined}>{l.label}</a>)}</nav><div className="pq-header-controls"><LocaleControl initial={locale} /><ThemeControl /><a href="/demo" className="pq-btn pq-btn-primary pq-header-cta">Explore demo <ArrowUpRight size={15} /></a></div></div></header>;
}
