"use client";

import {
  Activity, BarChart3, BookOpen, Boxes, ChevronRight, ClipboardCheck, Cog, FileClock, FlaskConical, GitBranch,
  Inbox, LayoutDashboard, LogIn, LogOut, Menu, PlusCircle, RotateCcw, ScrollText, ShieldCheck, Sparkles, Upload, User, Users, Wrench, X,
} from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState, type JSX, type ReactNode } from "react";

import { BrandLogo } from "@/components/BrandLogo";
import { LocaleControl } from "@/components/ui/LocaleControl";
import { ThemeControl } from "@/components/ui/ThemeControl";
import { useLocale, useT, type TKey } from "@/lib/app-i18n";
import { useSections, useSession, type PreviewRole } from "@/lib/session";
import type { Capability } from "@/lib/workspace";

import { Alert, ConfirmDialog, ErrorState, Skeleton, ToastProvider } from "./ui";

interface NavItem { href: string; label: TKey; icon: typeof Inbox; cap?: Capability; exact?: boolean }

const CUSTOMER_NAV: NavItem[] = [
  { href: "/workspace", label: "nav.dashboard", icon: LayoutDashboard, exact: true },
  { href: "/workspace/enquiries/new", label: "nav.new", icon: PlusCircle, cap: "enquiry.create", exact: true },
  { href: "/workspace/enquiries", label: "nav.enquiries", icon: Inbox, cap: "enquiry.read_own" },
  { href: "/workspace/machines", label: "nav.machines", icon: Wrench, cap: "machines.manage_own" },
];
const REVIEW_NAV: NavItem[] = [
  { href: "/workspace/review", label: "nav.review", icon: ClipboardCheck, cap: "review.queue" },
  { href: "/workspace/catalogue", label: "nav.catalogue", icon: Boxes, cap: "catalogue.browse" },
];
const ADMIN_NAV: NavItem[] = [
  { href: "/workspace/admin/users", label: "nav.users", icon: Users, cap: "admin.users" },
  { href: "/workspace/admin/imports", label: "nav.imports", icon: Upload, cap: "catalogue.import" },
  { href: "/workspace/admin/analytics", label: "nav.analytics", icon: BarChart3, cap: "analytics.read" },
  { href: "/workspace/admin/jobs", label: "nav.jobs", icon: Cog, cap: "jobs.read" },
  { href: "/workspace/admin/audit", label: "nav.audit", icon: ScrollText, cap: "audit.read" },
  { href: "/workspace/admin/evaluation", label: "nav.evaluation", icon: FlaskConical, cap: "evaluation.run" },
];

const CRUMB_LABELS: Record<string, TKey> = {
  enquiries: "nav.enquiries", new: "nav.new", machines: "nav.machines", review: "nav.review", catalogue: "nav.catalogue",
  admin: "nav.admin", users: "nav.users", imports: "nav.imports", analytics: "nav.analytics", jobs: "nav.jobs",
  audit: "nav.audit", evaluation: "nav.evaluation", account: "nav.account",
};

const CrumbContext = createContext<(label: string | null) => void>(() => undefined);

/** Pages with a dynamic id call this to show a readable last breadcrumb. */
export function useCrumb(label: string | null | undefined): void {
  const set = useContext(CrumbContext);
  useEffect(() => {
    set(label ?? null);
    return () => set(null);
  }, [label, set]);
}

function isActive(pathname: string, item: NavItem): boolean {
  if (item.exact) return pathname === item.href;
  return pathname === item.href || (pathname.startsWith(item.href + "/") && !pathname.startsWith("/workspace/enquiries/new"));
}

export function AppShell({ children }: { children: ReactNode }): JSX.Element {
  const session = useSession();
  return (
    <ToastProvider>
      {session.status === "ready" ? <Shell>{children}</Shell> : <Gate />}
    </ToastProvider>
  );
}

function Gate(): JSX.Element {
  const session = useSession();
  const t = useT();
  const router = useRouter();
  const pathname = usePathname();
  if (session.status === "loading") {
    return <div className="app-entry"><div className="app-entry-card"><BrandLogo /><Skeleton lines={3} height={18} /></div></div>;
  }
  const next = encodeURIComponent(pathname || "/workspace");
  return (
    <div className="app-entry">
      <section className="app-entry-card" id="main-workspace" aria-label="Sign in or start the demo">
        <BrandLogo />
        <h1>{t("entry.title")}</h1>
        {session.status === "expired" && <Alert tone="warn">{t("entry.expired")}</Alert>}
        {session.status === "error" && <ErrorState error={new Error(session.error ?? "The API could not be reached.")} onRetry={() => session.refresh()} />}
        <div className="app-grid">
          <section className="app-card">
            <h2 className="app-card-title"><Sparkles size={18} /> {t("entry.demo")}</h2>
            <p className="app-muted">{t("entry.demoBody")}</p>
            <button className="app-btn primary" data-testid="start-demo" onClick={() => session.startDemo()}>{t("entry.demo")}</button>
          </section>
          <section className="app-card">
            <h2 className="app-card-title"><LogIn size={18} /> {t("entry.signin")}</h2>
            <p className="app-muted">{t("entry.signinBody")}</p>
            <button className="app-btn" onClick={() => router.push(`/login?next=${next}`)}>{t("entry.signin")}</button>
          </section>
        </div>
        <p className="app-small app-muted">Independent portfolio project with a synthetic catalogue. No affiliation with any distributor is implied.</p>
      </section>
    </div>
  );
}

function Shell({ children }: { children: ReactNode }): JSX.Element {
  const session = useSession();
  const { demo, showReview, showAdmin } = useSections();
  const t = useT();
  const locale = useLocale();
  const pathname = usePathname() ?? "/workspace";
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [crumb, setCrumb] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const identity = session.identity!;

  useEffect(() => setOpen(false), [pathname]);

  const crumbs = useMemo(() => {
    const parts = pathname.split("/").filter(Boolean).slice(1);
    const out: { href: string; label: string }[] = [{ href: "/workspace", label: t("nav.workspace") }];
    let href = "/workspace";
    parts.forEach((part, index) => {
      href += `/${part}`;
      const known = CRUMB_LABELS[part];
      const isLast = index === parts.length - 1;
      if (part === "admin") return;
      out.push({ href, label: known ? t(known) : isLast && crumb ? crumb : `${part.slice(0, 8)}` });
    });
    return out;
  }, [pathname, crumb, t]);

  const visible = (items: NavItem[]) => items.filter((item) => !item.cap || session.can(item.cap));
  const nav = (items: NavItem[]) => (
    <nav className="app-nav">
      {visible(items).map((item) => (
        <a key={item.href} href={item.href} aria-current={isActive(pathname, item) ? "page" : undefined} onClick={(e) => { e.preventDefault(); router.push(item.href); }}>
          <item.icon size={17} aria-hidden="true" />{t(item.label)}
        </a>
      ))}
    </nav>
  );

  const roleOptions: { value: PreviewRole; label: string }[] = [
    { value: "customer", label: t("shell.customer") },
    { value: "reviewer", label: t("shell.reviewer") },
    { value: "admin", label: t("shell.admin") },
  ];

  return (
    <CrumbContext.Provider value={setCrumb}>
      <div className="app" data-nav-open={open ? "true" : "false"} data-entry={identity.kind}>
        <a className="app-skip" href="#main-workspace">{t("shell.skip")}</a>
        <aside className="app-rail" aria-label="Workspace navigation">
          <a className="app-brand" href="/" aria-label="PartsIQ home"><BrandLogo compact /><small>{t("nav.workspace")}</small></a>
          <p className="app-rail-label">{demo ? t("shell.customer") : t("nav.workspace")}</p>
          {nav(CUSTOMER_NAV)}
          {showReview && <><p className="app-rail-label">{t("shell.reviewer")}</p>{nav(REVIEW_NAV)}</>}
          {showAdmin && <><p className="app-rail-label">{t("nav.admin")}</p>{nav(ADMIN_NAV)}</>}
          <p className="app-rail-label">{t("nav.account")}</p>
          {nav([{ href: "/workspace/account", label: "nav.account", icon: User }])}
          <div className="app-rail-foot">
            <a href="/demo/scenarios"><GitBranch size={14} />{t("nav.scenarios")}</a>
            <a href="/architecture"><BookOpen size={14} />{t("nav.how")}</a>
          </div>
        </aside>
        {open && <div className="app-scrim" onClick={() => setOpen(false)} aria-hidden="true" />}
        <div className="app-main">
          <header className="app-top">
            <button className="app-btn ghost small app-menu-btn" aria-label={open ? t("shell.close") : t("shell.menu")} aria-expanded={open} onClick={() => setOpen(!open)}>{open ? <X size={18} /> : <Menu size={18} />}</button>
            <nav className="app-crumbs" aria-label="Breadcrumb">
              {crumbs.map((c, i) => (
                <span key={c.href} className="app-row" style={{ gap: 6 }}>
                  {i > 0 && <ChevronRight size={13} aria-hidden="true" />}
                  {i === crumbs.length - 1 ? <span aria-current="page">{c.label}</span> : <a href={c.href} onClick={(e) => { e.preventDefault(); router.push(c.href); }}>{c.label}</a>}
                </span>
              ))}
            </nav>
            <div className="app-top-actions">
              {demo ? (
                <>
                  <span className="app-mode demo app-hide-sm" data-testid="demo-indicator"><ShieldCheck size={14} />{t("shell.demo")}</span>
                  <label className="app-row" style={{ gap: 6 }}>
                    <select className="app-select" aria-label={t("shell.preview")} data-testid="preview-role" value={session.preview} onChange={(e) => session.setPreview(e.target.value as PreviewRole)}>
                      {roleOptions.map((o) => <option key={o.value} value={o.value}>{t("shell.preview")}: {o.label}</option>)}
                    </select>
                  </label>
                </>
              ) : (
                <span className="app-mode app-hide-sm"><Activity size={14} />{identity.display_name ?? identity.email ?? t("shell.account")}{identity.roles.length ? ` · ${identity.roles.join(", ")}` : ""}</span>
              )}
              <LocaleControl initial={locale} />
              <ThemeControl />
              {demo && <button className="app-btn small" onClick={() => setConfirmReset(true)} title={t("shell.reset")}><RotateCcw size={14} /><span className="app-hide-sm">{t("shell.reset")}</span></button>}
              <button className="app-btn small" onClick={async () => { await session.signOut(); router.push("/workspace"); }} data-testid="sign-out"><LogOut size={14} /><span className="app-hide-sm">{t("shell.signout")}</span></button>
            </div>
          </header>
          <div className="app-content" id="main-workspace" tabIndex={-1} role="region" aria-label="Workspace content">
            {children}
            <footer className="app-small app-muted" style={{ marginTop: 40, display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "space-between" }}>
              <span><FileClock size={12} /> Synthetic seed-42 catalogue · independent portfolio project</span>
              <span>Compatibility is checked in code. Every recommendation needs human approval.</span>
            </footer>
          </div>
        </div>
        <ConfirmDialog
          open={confirmReset}
          title="Reset this demo session?"
          body="Your synthetic enquiries, runs and sandbox changes are discarded and a fresh session starts. This cannot be undone."
          confirmLabel={t("shell.reset")}
          tone="danger"
          onCancel={() => setConfirmReset(false)}
          onConfirm={async () => { setConfirmReset(false); await session.resetDemo(); router.push("/workspace"); }}
        />
      </div>
    </CrumbContext.Provider>
  );
}
