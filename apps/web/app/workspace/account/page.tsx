"use client";

import { LogOut, RotateCcw, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import type { JSX } from "react";

import { LocaleControl } from "@/components/ui/LocaleControl";
import { ThemeControl } from "@/components/ui/ThemeControl";
import { Alert, Ident, PageHeader, useDates } from "@/components/app/ui";
import { useLabel, useLocale, useT } from "@/lib/app-i18n";
import { useSession } from "@/lib/session";

export default function AccountPage(): JSX.Element {
  const session = useSession();
  const router = useRouter();
  const locale = useLocale();
  const t = useT();
  const label = useLabel();
  const { time } = useDates();
  const me = session.identity!;
  return (
    <>
      <PageHeader title={t("nav.account")} description={t("acct.desc")} />
      <div className="app-grid cols-2">
        <section className="app-card">
          <h2 className="app-card-title"><ShieldCheck size={16} />{t("acct.identity")}</h2>
          <dl className="app-kv">
            <dt>{t("acct.type")}</dt><dd>{me.kind === "demo" ? t("acct.typeDemo") : t("acct.typeAccount")}</dd>
            {me.email && <><dt>{t("common.email")}</dt><dd><bdi dir="ltr">{me.email}</bdi></dd></>}
            <dt>{t("acct.userId")}</dt><dd><Ident>{me.id}</Ident></dd>
            <dt>{t("acct.roles")}</dt><dd>{me.roles.length ? me.roles.map((r) => label("role", r)).join(locale === "ar" ? "، " : ", ") : me.kind === "demo" ? t("acct.rolesNone") : t("role.customer")}</dd>
            {me.kind === "demo" && <><dt>{t("acct.demoSession")}</dt><dd><Ident>{me.demo_session_id?.slice(0, 8)}</Ident> · {t("acct.generation", { n: me.demo_session_generation ?? "—" })}</dd><dt>{t("acct.expires")}</dt><dd>{time(me.demo_expires_at)}</dd></>}
            <dt>{t("acct.data")}</dt><dd>{me.data_source === "fixture" ? t("acct.dataFixture") : <bdi>{me.data_source}</bdi>}</dd>
            <dt>{t("acct.ai")}</dt><dd>{me.live_available ? t("acct.aiLive") : t("acct.aiFixture")}</dd>
          </dl>
          {me.kind === "demo" && <Alert tone="info">{t("acct.demoNote")}</Alert>}
        </section>
        <section className="app-card">
          <h2 className="app-card-title">{t("acct.capabilities")}</h2>
          <div className="app-row">{me.capabilities.map((c) => <bdi key={c} className="app-badge outline app-mono">{c}</bdi>)}</div>
          <hr className="app-divider" />
          <h2 className="app-card-title">{t("acct.preferences")}</h2>
          <div className="app-row"><LocaleControl initial={locale} /><ThemeControl /></div>
          <p className="app-small app-muted">{t("acct.prefsNote")}</p>
          <hr className="app-divider" />
          <div className="app-row">
            {me.kind === "demo" && <button className="app-btn" onClick={async () => { await session.resetDemo(); router.push("/workspace"); }}><RotateCcw size={15} />{t("acct.resetDemo")}</button>}
            <button className="app-btn danger" onClick={async () => { await session.signOut(); router.push("/workspace"); }}><LogOut size={15} />{t("shell.signout")}</button>
          </div>
        </section>
      </div>
    </>
  );
}
