"use client";

import Link from "next/link";
import { KeyRound, LogIn, Mail, Sparkles } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type JSX } from "react";

import { BrandLogo } from "@/components/BrandLogo";
import { Alert, Skeleton } from "@/components/app/ui";
import { useT } from "@/lib/app-i18n";
import { accountsConfigured } from "@/lib/session";

// Invited accounts only (customers, reviewers, administrators). There is deliberately no public
// signup: accounts are created by an administrator invitation (Supabase sends a one-time link).
export default function LoginPage(): JSX.Element {
  return <Suspense fallback={<div className="app-entry"><Skeleton lines={3} /></div>}><Login /></Suspense>;
}

function safeNext(value: string | null): string {
  // Only same-site workspace paths are honoured (no open redirect).
  return value && value.startsWith("/workspace") && !value.startsWith("//") ? value : "/workspace";
}

function Login(): JSX.Element {
  const router = useRouter();
  const t = useT();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [mode, setMode] = useState<"password" | "link" | "set">("password");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const configured = accountsConfigured();

  useEffect(() => {
    if (!configured) return;
    // Invitation / recovery links land here with a one-time session in the URL fragment. The SSR
    // client uses PKCE and ignores implicit fragments, so establish that session explicitly, remove
    // the tokens from the address bar, then ask the user to choose a password.
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const access = hash.get("access_token");
    const refresh = hash.get("refresh_token");
    if (access && refresh && /invite|recovery|magiclink/.test(hash.get("type") ?? "")) {
      window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
      import("@/lib/auth").then(async ({ browserClient }) => {
        const { error: err } = await browserClient().auth.setSession({ access_token: access, refresh_token: refresh });
        if (err) setError(t("login.linkExpired"));
        else if (hash.get("type") === "magiclink") finish();
        else setMode("set");
      });
    } else if (params.get("invited") === "1") {
      setMode("set");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [configured, params]);

  const finish = () => {
    try { window.localStorage.setItem("pq-entry", "account"); } catch { /* optional */ }
    router.replace(next);
  };

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null); setInfo(null); setBusy(true);
    try {
      const { browserClient } = await import("@/lib/auth");
      const auth = browserClient().auth;
      if (mode === "password") {
        const { error: err } = await auth.signInWithPassword({ email, password });
        if (err) throw err;
        finish();
      } else if (mode === "link") {
        const redirect = `${window.location.origin}/login?next=${encodeURIComponent(next)}`;
        const { error: err } = await auth.signInWithOtp({ email, options: { shouldCreateUser: false, emailRedirectTo: redirect } });
        if (err) throw err;
        setInfo(t("login.linkSent"));
      } else {
        if (newPassword.length < 10) throw new Error(t("login.tooShort"));
        const { error: err } = await auth.updateUser({ password: newPassword });
        if (err) throw err;
        finish();
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : t("login.failed");
      setError(mode === "password" ? t("login.failedPassword") : message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-entry">
      <section className="app-entry-card" style={{ maxWidth: 460 }} aria-label={t("entry.signin")}>
        <BrandLogo />
        <h1>{mode === "set" ? t("login.setTitle") : t("entry.signin")}</h1>
        <p className="app-muted">{t("login.subtitle")}</p>
        {!configured ? (
          <>
            <Alert tone="warn" title={t("login.notConfigured")}>{t("login.notConfiguredBody")}</Alert>
            <Link className="app-btn primary" href="/demo"><Sparkles size={15} />{t("login.tryDemo")}</Link>
          </>
        ) : (
          <form className="app-card app-stack" onSubmit={submit}>
            {mode !== "set" && (
              <div className="app-seg" role="group" aria-label={t("login.methodAria")}>
                <button type="button" aria-pressed={mode === "password"} onClick={() => setMode("password")}><KeyRound size={14} /> {t("login.password")}</button>
                <button type="button" aria-pressed={mode === "link"} onClick={() => setMode("link")}><Mail size={14} /> {t("login.emailLink")}</button>
              </div>
            )}
            {mode !== "set" && <label className="app-field"><span>{t("common.email")}</span><input className="app-input" type="email" dir="ltr" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="login-email" /></label>}
            {mode === "password" && <label className="app-field"><span>{t("login.password")}</span><input className="app-input" type="password" dir="ltr" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required data-testid="login-password" /></label>}
            {mode === "set" && <label className="app-field"><span>{t("login.newPassword")}</span><input className="app-input" type="password" dir="ltr" autoComplete="new-password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required minLength={10} /><small>{t("login.minChars")}</small></label>}
            {error && <Alert tone="danger"><span dir="auto">{error}</span></Alert>}
            {info && <Alert tone="ok">{info}</Alert>}
            <button className="app-btn primary" type="submit" disabled={busy} data-testid="login-submit"><LogIn size={15} />{busy ? t("login.wait") : mode === "link" ? t("login.sendLink") : mode === "set" ? t("login.savePassword") : t("entry.signin")}</button>
          </form>
        )}
        <Link className="app-small" href="/">{t("login.back")}</Link>
      </section>
    </div>
  );
}
