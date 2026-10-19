// lib/live reviewer-side functions + ensureDemoToken. Exercises the REAL api<T> path with a mocked
// fetch so we assert the exact method/body/headers each function sends, and that ensureDemoToken
// persists one session token and attaches it as X-Demo-Token on subsequent calls.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, setDemoToken } from "@/lib/api";
import {
  approveReview,
  ensureDemoToken,
  getWorkspace,
  listInbox,
  rejectReview,
  type ApprovalResult,
  type ReviewResult,
  type ReviewView,
} from "@/lib/live";

function jsonResponse(body: unknown, init: { status?: number; requestId?: string } = {}): Response {
  const headers = new Headers({ "content-type": "application/json" });
  if (init.requestId) headers.set("x-request-id", init.requestId);
  return new Response(JSON.stringify(body), { status: init.status ?? 200, headers });
}

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  // Reset demo identity between tests and clear the persisted session token.
  setDemoToken(null);
  window.sessionStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function lastCall(): [string, RequestInit] {
  const call = fetchMock.mock.calls.at(-1);
  return [String(call?.[0]), (call?.[1] ?? {}) as RequestInit];
}

function headerBag(init: RequestInit): Record<string, string> {
  const bag: Record<string, string> = {};
  new Headers(init.headers).forEach((v, k) => (bag[k] = v));
  return bag;
}

describe("ensureDemoToken (F04 one-session isolation)", () => {
  it("generates and persists exactly one session token, reusing it on later calls", () => {
    const first = ensureDemoToken();
    expect(first).toMatch(/[0-9a-f-]{36}/i);
    expect(window.sessionStorage.getItem("pq-demo-token")).toBe(first);
    const second = ensureDemoToken();
    expect(second).toBe(first); // same session → same token, never regenerated
  });

  it("attaches the token as X-Demo-Token on subsequent api calls", async () => {
    const token = ensureDemoToken();
    fetchMock.mockResolvedValueOnce(jsonResponse({ items: [], next_cursor: null }));
    await listInbox("awaiting_review");
    const [, init] = lastCall();
    expect(headerBag(init)["x-demo-token"]).toBe(token);
  });
});

describe("listInbox", () => {
  it("requests the own-session staff queue filtered by status", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ items: [], next_cursor: null }));
    const result = await listInbox("awaiting_review");
    const [url, init] = lastCall();
    expect(url).toContain("/v1/staff/enquiries?status=awaiting_review");
    expect(init.method ?? "GET").toBe("GET");
    expect(result).toEqual({ items: [], next_cursor: null });
  });

  it("omits the query when no status is given", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ items: [], next_cursor: null }));
    await listInbox();
    const [url] = lastCall();
    expect(url).toMatch(/\/v1\/staff\/enquiries$/);
  });
});

describe("getWorkspace", () => {
  it("fetches the review workspace resource", async () => {
    const view: ReviewView = {
      enquiry: { id: "e1", revision: 3, status: "awaiting_review", messages: [], item_ids: [], catalogue_version_id: null, updated_at: "t" },
      facts: { items: [] },
      draft: { greeting: "Hi", explanation: "...", closing: "Thanks" },
      verification: { passed: true, failures: [], facts_sha256: "a".repeat(64) },
      assigned_to: null,
    };
    fetchMock.mockResolvedValueOnce(jsonResponse(view));
    const got = await getWorkspace("e1");
    const [url] = lastCall();
    expect(url).toContain("/v1/staff/enquiries/e1");
    expect(got.enquiry.revision).toBe(3);
  });

  it("surfaces a foreign enquiry as a 404 ApiError (not available)", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ code: "NOT_FOUND", detail: "nope", request_id: "req-404" }, { status: 404, requestId: "req-404" }));
    await expect(getWorkspace("foreign")).rejects.toMatchObject({ status: 404 });
  });
});

describe("approveReview", () => {
  it("POSTs the expected revision + a generated draft_id with an idempotency key, once", async () => {
    const result: ApprovalResult = { decision_id: "d1", message_id: "m1", revision: 4, already_applied: false };
    fetchMock.mockResolvedValueOnce(jsonResponse(result));
    const got = await approveReview("e1", 3);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = lastCall();
    expect(url).toContain("/v1/staff/enquiries/e1/approve");
    expect(init.method).toBe("POST");
    const body = JSON.parse(String(init.body));
    expect(body).toMatchObject({ enquiry_id: "e1", expected_revision: 3 });
    expect(body.draft_id).toMatch(/[0-9a-f-]{36}/i);
    expect(headerBag(init)["idempotency-key"]).toBeTruthy();
    expect(got.revision).toBe(4);
  });
});

describe("rejectReview", () => {
  it("POSTs the reason with the expected revision and an idempotency key", async () => {
    const result: ReviewResult = { decision_id: "d2", revision: 4, status: "rejected" };
    fetchMock.mockResolvedValueOnce(jsonResponse(result));
    const got = await rejectReview("e1", 3, "part does not fit");

    const [url, init] = lastCall();
    expect(url).toContain("/v1/staff/enquiries/e1/reject");
    expect(init.method).toBe("POST");
    const body = JSON.parse(String(init.body));
    expect(body).toMatchObject({ enquiry_id: "e1", expected_revision: 3, reason: "part does not fit" });
    expect(headerBag(init)["idempotency-key"]).toBeTruthy();
    expect(got.status).toBe("rejected");
  });

  it("propagates a 409 as an ApiError so the caller can preserve input", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ code: "CONFLICT", detail: "stale", request_id: "req-409" }, { status: 409, requestId: "req-409" }));
    await expect(rejectReview("e1", 1, "reason")).rejects.toBeInstanceOf(ApiError);
  });
});
