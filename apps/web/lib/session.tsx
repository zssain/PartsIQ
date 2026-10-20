"use client";

// Session layer for the workspace (ADR 0002).
//
// Two distinct entry paths, never mixed:
//  * PUBLIC DEMO — an opaque random X-Demo-Token kept in localStorage (one sandbox per browser).
//    The server scopes it to a disposable synthetic workspace; it never carries a staff role.
//  * INVITED ACCOUNT — a Supabase Auth session (restored on refresh, refreshed automatically by
//    @supabase/ssr). The bearer token is the only credential; the demo token is not sent.
//
// Identity and capabilities ALWAYS come from GET /v1/me. Navigation is built from those server
// capabilities; a role-preview selector (demo only) changes which screens are shown, not what the
// server allows. When identity changes (sign-in, sign-out, demo reset) every cached screen is
// discarded via the `epoch` counter so stale protected data is never rendered.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type JSX, type ReactNode } from "react";

import { ApiError, setDemoToken, setTokenProvider } from "@/lib/api";
import { ws, type Capability, type Identity } from "@/lib/workspace";

export type EntryKind = "demo" | "account";
export type PreviewRole = "customer" | "reviewer" | "admin";
export type SessionStatus = "loading" | "ready" | "signed_out" | "expired" | "error";

const DEMO_TOKEN_KEY = "pq-demo-token";
const ENTRY_KEY = "pq-entry";
const PREVIEW_KEY = "pq-preview-role";

interface SessionValue {
  status: SessionStatus;
  identity: Identity | null;
  entry: EntryKind | null;
  preview: PreviewRole;
  epoch: number;
  error: string | null;
  accountsConfigured: boolean;
  can: (cap: Capability) => boolean;
  setPreview: (role: PreviewRole) => void;
  startDemo: () => Promise<void>;
  signOut: () => Promise<void>;
  resetDemo: () => Promise<void>;
  refresh: () => Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function demoToken(create: boolean): string | null {
  const store = storage();
  let token = store?.getItem(DEMO_TOKEN_KEY) ?? null;
  if (!token) {
    try {
      token = window.sessionStorage.getItem(DEMO_TOKEN_KEY); // migrate the older per-tab token
    } catch {
      token = null;
    }
  }
  if (!token && create) token = crypto.randomUUID();
  if (token) store?.setItem(DEMO_TOKEN_KEY, token);
  return token;
}

export function accountsConfigured(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY);
}

async function supabaseSession(): Promise<string | null> {
  if (!accountsConfigured()) return null;
  const { browserClient } = await import("@/lib/auth");
  const { data } = await browserClient().auth.getSession();
  return data.session?.access_token ?? null;
}

export function SessionProvider({ children }: { children: ReactNode }): JSX.Element {
  const [status, setStatus] = useState<SessionStatus>("loading");
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [entry, setEntry] = useState<EntryKind | null>(null);
  const [preview, setPreviewState] = useState<PreviewRole>("customer");
  const [epoch, setEpoch] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const lastIdentity = useRef<string | null>(null);

  const load = useCallback(async (kind: EntryKind) => {
    setStatus("loading");
    setError(null);
    if (kind === "demo") {
      setTokenProvider(async () => null);
      setDemoToken(demoToken(true));
    } else {
      setDemoToken(null);
      const { browserClient } = await import("@/lib/auth");
      setTokenProvider(async () => (await browserClient().auth.getSession()).data.session?.access_token ?? null);
    }
    try {
      const me = await ws.me();
      const key = `${me.kind}:${me.id}:${me.demo_session_id ?? ""}:${me.demo_session_generation ?? ""}`;
      if (lastIdentity.current !== key) {
        lastIdentity.current = key;
        setEpoch((n) => n + 1); // identity changed: drop every cached screen
      }
      setIdentity(me);
      setEntry(kind);
      setStatus("ready");
    } catch (err) {
      setIdentity(null);
      if (err instanceof ApiError && err.status === 401) {
        setStatus(kind === "account" ? "expired" : "signed_out");
      } else {
        setStatus("error");
        setError(err instanceof ApiError ? `${err.message}${err.requestId ? ` (request ${err.requestId})` : ""}` : "The API could not be reached.");
      }
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const stored = storage()?.getItem(ENTRY_KEY) as EntryKind | null;
      const savedPreview = storage()?.getItem(PREVIEW_KEY) as PreviewRole | null;
      if (savedPreview) setPreviewState(savedPreview);
      const params = new URLSearchParams(window.location.search);
      const token = await supabaseSession().catch(() => null);
      if (cancelled) return;
      if (token && stored !== "demo") {
        storage()?.setItem(ENTRY_KEY, "account");
        await load("account");
      } else if (stored === "demo" || params.get("demo") === "1" || demoToken(false)) {
        storage()?.setItem(ENTRY_KEY, "demo");
        await load("demo");
      } else {
        setStatus("signed_out");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  // Supabase token refresh / sign-out in another tab.
  useEffect(() => {
    if (!accountsConfigured()) return;
    let unsubscribe: (() => void) | undefined;
    import("@/lib/auth").then(({ browserClient }) => {
      const { data } = browserClient().auth.onAuthStateChange((event) => {
        if (entry !== "account") return;
        if (event === "SIGNED_OUT") {
          lastIdentity.current = null;
          setIdentity(null);
          setEpoch((n) => n + 1);
          setStatus("signed_out");
        } else if (event === "TOKEN_REFRESHED" || event === "SIGNED_IN") {
          void load("account");
        }
      });
      unsubscribe = () => data.subscription.unsubscribe();
    });
    return () => unsubscribe?.();
  }, [entry, load]);

  // Any protected 401 means the session ended: stop showing data and ask to sign in again.
  useEffect(() => {
    const onUnauthorized = () => {
      if (status !== "ready") return;
      setIdentity(null);
      setEpoch((n) => n + 1);
      setStatus(entry === "account" ? "expired" : "signed_out");
    };
    window.addEventListener("pq:unauthorized", onUnauthorized);
    return () => window.removeEventListener("pq:unauthorized", onUnauthorized);
  }, [status, entry]);

  const value = useMemo<SessionValue>(() => ({
    status,
    identity,
    entry,
    preview: identity?.kind === "account" ? "customer" : preview,
    epoch,
    error,
    accountsConfigured: accountsConfigured(),
    can: (cap) => Boolean(identity?.capabilities.includes(cap)),
    setPreview: (role) => {
      setPreviewState(role);
      storage()?.setItem(PREVIEW_KEY, role);
    },
    startDemo: async () => {
      storage()?.setItem(ENTRY_KEY, "demo");
      await load("demo");
    },
    signOut: async () => {
      if (entry === "account" && accountsConfigured()) {
        const { browserClient } = await import("@/lib/auth");
        await browserClient().auth.signOut();
      }
      storage()?.removeItem(ENTRY_KEY);
      setTokenProvider(async () => null);
      setDemoToken(null);
      lastIdentity.current = null;
      setIdentity(null);
      setEpoch((n) => n + 1);
      setStatus("signed_out");
    },
    resetDemo: async () => {
      if (!identity?.demo_session_id) return;
      await ws.resetDemo(identity.demo_session_id, crypto.randomUUID());
      await load("demo");
    },
    refresh: async () => {
      if (entry) await load(entry);
    },
  }), [status, identity, entry, preview, epoch, error, load]);

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}

/** Which workspace sections a caller sees: the server capability AND (demo only) the preview. */
export function useSections() {
  const { can, identity, preview } = useSession();
  const demo = identity?.kind === "demo";
  const showReview = can("review.queue") && (!demo || preview !== "customer");
  const showAdmin = (can("admin.users") || can("catalogue.import") || can("analytics.read")) && (!demo || preview === "admin");
  return { demo, showReview, showAdmin };
}
