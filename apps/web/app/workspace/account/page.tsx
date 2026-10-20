"use client";

import { LogOut, RotateCcw, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import type { JSX } from "react";

import { LocaleControl } from "@/components/ui/LocaleControl";
import { ThemeControl } from "@/components/ui/ThemeControl";
import { Alert, Ident, PageHeader, formatTime } from "@/components/app/ui";
import { useLocale } from "@/lib/app-i18n";
import { useSession } from "@/lib/session";

export default function AccountPage(): JSX.Element {
  const session = useSession();
  const router = useRouter();
  const locale = useLocale();
  const me = session.identity!;
  return (
    <>
      <PageHeader title="Account" description="Your identity and what the server allows you to do. Navigation is built from these server-granted capabilities." />
      <div className="app-grid cols-2">
        <section className="app-card">
          <h2 className="app-card-title"><ShieldCheck size={16} />Identity</h2>
          <dl className="app-kv">
            <dt>Type</dt><dd>{me.kind === "demo" ? "Public demo visitor (anonymous)" : "Invited account (Supabase)"}</dd>
            {me.email && <><dt>Email</dt><dd>{me.email}</dd></>}
            <dt>User id</dt><dd><Ident>{me.id}</Ident></dd>
            <dt>Roles</dt><dd>{me.roles.length ? me.roles.join(", ") : me.kind === "demo" ? "None (sandbox only)" : "Customer"}</dd>
            {me.kind === "demo" && <><dt>Demo session</dt><dd><Ident>{me.demo_session_id?.slice(0, 8)}</Ident> · generation {me.demo_session_generation}</dd><dt>Expires</dt><dd>{formatTime(me.demo_expires_at)}</dd></>}
            <dt>Data</dt><dd>{me.data_source === "fixture" ? "Synthetic seed-42 catalogue" : me.data_source}</dd>
            <dt>AI</dt><dd>{me.live_available ? "Live provider available" : "Fixture replay (no live model calls)"}</dd>
          </dl>
          {me.kind === "demo" && <Alert tone="info">A demo session expires after 24 hours or when you reset it. Its data is never shared with anyone else.</Alert>}
        </section>
        <section className="app-card">
          <h2 className="app-card-title">Server capabilities</h2>
          <div className="app-row">{me.capabilities.map((c) => <span key={c} className="app-badge outline app-mono">{c}</span>)}</div>
          <hr className="app-divider" />
          <h2 className="app-card-title">Preferences</h2>
          <div className="app-row"><LocaleControl initial={locale} /><ThemeControl /></div>
          <p className="app-small app-muted">Language and theme are stored in this browser.</p>
          <hr className="app-divider" />
          <div className="app-row">
            {me.kind === "demo" && <button className="app-btn" onClick={async () => { await session.resetDemo(); router.push("/workspace"); }}><RotateCcw size={15} />Reset demo session</button>}
            <button className="app-btn danger" onClick={async () => { await session.signOut(); router.push("/workspace"); }}><LogOut size={15} />Sign out</button>
          </div>
        </section>
      </div>
    </>
  );
}
