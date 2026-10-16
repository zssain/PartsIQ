// F53 Graceful failures — the api client maps stable error codes safely with the request id.
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, ApiError } from "@/lib/api";

function mockFetch(status: number, body: unknown, requestId = "req-1") {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: status < 400,
    status,
    statusText: "",
    headers: { get: (k: string) => (k.toLowerCase() === "x-request-id" ? requestId : null) },
    json: async () => body,
  }) as unknown as typeof fetch;
}

describe("api graceful failures (F53)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("maps a 503 envelope to a typed ApiError with the request id and a safe message", async () => {
    mockFetch(503, { error: { code: "DEPENDENCY_UNAVAILABLE", message: "A required service is temporarily unavailable." } });
    await expect(api("/v1/enquiries/x")).rejects.toMatchObject({
      code: "DEPENDENCY_UNAVAILABLE",
      status: 503,
      requestId: "req-1",
    });
  });

  it("surfaces a 422 validation code distinctly", async () => {
    mockFetch(422, { error: { code: "VALIDATION_FAILED", message: "One or more fields are invalid." } });
    const err = await api("/v1/enquiries").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("VALIDATION_FAILED");
    expect(err.message).not.toMatch(/traceback|stack|at /i); // no raw stack trace leaked
  });

  it("stays safe when the error body is not JSON", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 500, statusText: "Server Error",
      headers: { get: () => null },
      json: async () => {
        throw new Error("not json");
      },
    }) as unknown as typeof fetch;
    const err = await api("/v1/x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("DEPENDENCY_UNAVAILABLE"); // safe default, no leak
  });
});
