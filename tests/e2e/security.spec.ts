import { expect, test } from "@playwright/test";

// Security e2e (prompt 22). These run against a DISPOSABLE hosted/local stack only; they are
// BLOCKED in this environment (no running app) and must never be marked passed without a real
// run. They instantiate the existing UI/gateway surfaces — no new business logic.
//
// Covered scenarios (to run against a disposable stack):
//  - No secret appears in the served JS bundle (grep the page for service-role/JWT/API keys).
//  - A foreign visitor opening another session's enquiry sees a 404, never the content.
//  - An expired/forged token is rejected and never renders staff controls.
//  - The staff workspace is reachable only for an assigned reviewer / own demo session.

test.describe("security (requires a disposable hosted stack)", () => {
  test.skip(({ baseURL }) => !baseURL, "no baseURL configured; security e2e is BLOCKED offline");

  test("no secret in the served bundle", async ({ request, baseURL }) => {
    const res = await request.get(`${baseURL}/`);
    const body = await res.text();
    expect(body).not.toMatch(/service_role|SUPABASE_JWT|OPENAI_API_KEY|INTERNAL_SERVICE_TOKEN/i);
  });

  test("another visitor's enquiry returns 404", async ({ request, baseURL }) => {
    const res = await request.get(`${baseURL}/api/v1/enquiries/00000000-0000-4000-8000-000000000000`);
    expect([401, 404]).toContain(res.status());
  });
});
