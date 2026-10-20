// Unified workspace (ADR 0002): navigation mirrors SERVER capabilities, protected screens refuse
// without them, retries reuse their idempotency key, run events are de-duplicated by sequence and
// polling stops on a terminal permission error, and unmeasured values are labelled honestly.
import { act, render, renderHook, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: push, refresh: vi.fn() }),
  usePathname: () => "/workspace",
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
}));

import { AppShell } from "@/components/app/AppShell";
import { SourceBadge } from "@/components/app/ui";
import { ApiError } from "@/lib/api";
import { AppLocaleProvider } from "@/lib/app-i18n";
import { useIdempotentAction, useRunEvents } from "@/lib/hooks";
import { SessionProvider } from "@/lib/session";
import AnalyticsPage from "@/app/workspace/admin/analytics/page";

function identity(over: Record<string, unknown>) {
  return {
    id: "u1", roles: [], is_anonymous: false, kind: "account", display_name: "Casey", email: "c@example.test",
    capabilities: ["enquiry.create", "enquiry.read_own", "machines.manage_own", "run.control_own"],
    demo_session_id: null, demo_session_generation: null, demo_expires_at: null, data_source: "fixture",
    ai_mode: "fixture", live_available: false, collaboration_enabled: true, ...over,
  };
}

const DEMO_CAPS = ["enquiry.create", "enquiry.read_own", "machines.manage_own", "run.control_own", "review.queue", "review.decide", "catalogue.browse", "catalogue.import", "admin.users", "analytics.read", "audit.read", "jobs.read", "evaluation.run"];

function mockApi(me: Record<string, unknown>, extra: Record<string, unknown> = {}) {
  const fetchMock = vi.fn(async (url: string) => {
    const path = new URL(url, "http://x").pathname;
    const body = path === "/v1/me" ? me : extra[path] ?? {};
    return new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const wrap = (children: ReactNode) => <AppLocaleProvider locale="en"><SessionProvider>{children}</SessionProvider></AppLocaleProvider>;

describe("workspace shell", () => {
  beforeEach(() => { localStorage.clear(); sessionStorage.clear(); });
  afterEach(() => vi.unstubAllGlobals());

  it("shows the entry screen (demo or sign in) when nobody is signed in", async () => {
    mockApi(identity({}));
    render(wrap(<AppShell><p>content</p></AppShell>));
    expect(await screen.findByTestId("start-demo")).toBeInTheDocument();
    expect(screen.queryByText("content")).toBeNull();
  });

  it("builds navigation from server capabilities and the demo role preview", async () => {
    localStorage.setItem("pq-entry", "demo");
    mockApi(identity({ kind: "demo", is_anonymous: true, capabilities: DEMO_CAPS, demo_session_id: "s1", demo_session_generation: 1 }));
    render(wrap(<AppShell><p>content</p></AppShell>));
    expect(await screen.findByText("content")).toBeInTheDocument();
    expect(screen.getByTestId("demo-indicator")).toHaveTextContent(/synthetic/i);
    // Customer preview: no review/admin sections even though the sandbox would allow them.
    expect(screen.queryByRole("link", { name: /review queue/i })).toBeNull();
    act(() => { (screen.getByTestId("preview-role") as HTMLSelectElement).value = "admin"; screen.getByTestId("preview-role").dispatchEvent(new Event("change", { bubbles: true })); });
    expect(await screen.findByRole("link", { name: /users & access/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /review queue/i })).toBeInTheDocument();
  });

  it("never shows staff navigation to a customer account, whatever is stored locally", async () => {
    localStorage.setItem("pq-preview-role", "admin");
    localStorage.setItem("pq-entry", "demo");
    mockApi(identity({ kind: "account" }));
    render(wrap(<AppShell><p>content</p></AppShell>));
    expect(await screen.findByText("content")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /review queue/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /users & access/i })).toBeNull();
    expect(screen.queryByTestId("preview-role")).toBeNull();
  });

  it("direct navigation to an admin screen without the capability shows a permission state", async () => {
    localStorage.setItem("pq-entry", "demo");
    mockApi(identity({ kind: "account" }));
    render(wrap(<AppShell><AnalyticsPage /></AppShell>));
    expect(await screen.findByText(/don't have access/i)).toBeInTheDocument();
  });

  it("labels fixture replay honestly and never as live AI", () => {
    render(<SourceBadge source="fixture" />);
    expect(screen.getByText(/fixture replay · no model calls/i)).toBeInTheDocument();
  });
});

describe("analytics honesty", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("renders unmeasured values as 'Not measured', not zero", async () => {
    localStorage.setItem("pq-entry", "demo");
    mockApi(identity({ kind: "demo", capabilities: DEMO_CAPS, demo_session_id: "s1", demo_session_generation: 1 }), {
      "/v1/admin/analytics": {
        scope: "demo", scope_note: "Only this demo session.", enquiries: { total: 0, by_status: {} },
        runs: { total: 0, by_mode: {}, failed: 0, retries: 0, cancelled: 0 }, exchanges: 0,
        review_seconds: { median: null, p95: null, samples: 0 }, latency_ms: {}, tokens: null,
        tokens_note: "Not measured: no live model calls were made (fixture execution).", allowance: null,
        allowance_note: "Unavailable: no confirmed live AI allowance is configured.", accuracy: null,
        accuracy_note: "Not measured: run the labelled evaluation.", demo_workspaces_active: null,
      },
    });
    render(wrap(<AppShell><AnalyticsPage /></AppShell>));
    await screen.findByTestId("analytics-stats");
    expect(screen.getAllByText(/not measured/i).length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText(/no confirmed live ai allowance/i)).toBeInTheDocument();
  });
});

describe("idempotent actions", () => {
  it("reuses the key after a network failure and renews it after a definitive answer", async () => {
    const keys: string[] = [];
    let attempt = 0;
    const fn = async (key: string) => {
      keys.push(key);
      attempt += 1;
      if (attempt === 1) throw new TypeError("Failed to fetch");
      if (attempt === 2) return "ok";
      throw new ApiError("VALIDATION_FAILED", 422, "bad", null);
    };
    const { result } = renderHook(() => useIdempotentAction(fn));
    await act(async () => { await result.current.run(); });
    await act(async () => { await result.current.run(); });
    expect(keys[0]).toBe(keys[1]); // same logical action retried → same key
    await act(async () => { await result.current.run(); });
    expect(keys[2]).not.toBe(keys[1]); // success renewed the key
  });
});

describe("run event polling", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("de-duplicates events by sequence and stops on a terminal permission error", async () => {
    localStorage.setItem("pq-entry", "demo");
    const run = { id: "r1", status: "running", revision: 1, state_version: 1 };
    let call = 0;
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      const path = new URL(url, "http://x").pathname;
      if (path === "/v1/me") return new Response(JSON.stringify(identity({ kind: "demo", capabilities: DEMO_CAPS, demo_session_id: "s", demo_session_generation: 1 })), { status: 200 });
      call += 1;
      if (call >= 3) return new Response(JSON.stringify({ code: "NOT_FOUND", detail: "gone" }), { status: 404 });
      // The same event is returned twice (reconnect overlap) — it must appear once.
      return new Response(JSON.stringify({ items: [{ id: "e1", seq: 1, kind: "task" }], next_after: 1, run }), { status: 200 });
    }));
    const { result } = renderHook(() => useRunEvents("r1"), { wrapper: ({ children }) => wrap(children) });
    await waitFor(() => expect(result.current.stopped).toBe(true), { timeout: 8000 });
    expect(result.current.events.map((e) => e.seq)).toEqual([1]);
    expect(result.current.error).toBeInstanceOf(ApiError);
  });
});
