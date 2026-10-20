// Invited-account journeys against a RUNNING stack with a real Supabase Auth (GoTrue) service.
// Invitation links come from tools/provision_accounts.py --links-only (file in E2E_INVITES).
// Passwords are generated here for this run only and never printed or stored.
// Env: E2E_BASE_URL, E2E_INVITES, E2E_OUT. Run: node tests/e2e/accounts.mjs
import { randomBytes } from "node:crypto";
import { mkdirSync, readFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const OUT = process.env.E2E_OUT ?? "/tmp/partsiq-accounts";
mkdirSync(OUT, { recursive: true });
const links = Object.fromEntries(
  readFileSync(process.env.E2E_INVITES, "utf8").split("\n")
    .map((line) => line.match(/invite link for (\S+) .*?: (\S+)/)).filter(Boolean).map((m) => [m[1], m[2]]),
);
const results = [];
const check = (name, ok, detail = "") => results.push({ name, ok: Boolean(ok), detail });
const passwords = {};

async function acceptInvite(browser, email) {
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(links[email]);
  await page.waitForURL(/\/login/, { timeout: 20000 });
  await page.getByRole("heading", { name: /set your password/i }).waitFor({ timeout: 20000 });
  passwords[email] = `${randomBytes(12).toString("base64url")}Aa1!`;
  await page.locator('input[type="password"]').fill(passwords[email]);
  await page.getByTestId("login-submit").click();
  await page.waitForURL(/\/workspace/, { timeout: 20000 });
  await page.locator(".app-rail").waitFor({ timeout: 20000 });
  return { ctx, page };
}

async function login(browser, email, next = "") {
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/login${next ? `?next=${encodeURIComponent(next)}` : ""}`);
  await page.getByTestId("login-email").fill(email);
  await page.getByTestId("login-password").fill(passwords[email]);
  await page.getByTestId("login-submit").click();
  await page.waitForURL(/\/workspace/, { timeout: 20000 });
  await page.locator(".app-rail").waitFor({ timeout: 20000 });
  return { ctx, page };
}

const browser = await chromium.launch();
try {
  // 1. Every invited persona redeems the invitation and chooses a password.
  const sessions = {};
  for (const email of ["customer@example.test", "reviewer@example.test", "admin@example.test"]) {
    sessions[email] = await acceptInvite(browser, email);
    const kind = await sessions[email].page.locator("[data-entry]").getAttribute("data-entry");
    check(`${email} signs in through the invitation`, kind === "account", kind ?? "");
  }
  const customer = sessions["customer@example.test"].page;
  const reviewer = sessions["reviewer@example.test"].page;
  const admin = sessions["admin@example.test"].page;

  // 2. Customer: own enquiry; no staff navigation; staff screens and APIs refused.
  await customer.goto(`${BASE}/workspace/enquiries/new`);
  await customer.getByTestId("enquiry-text").fill("Need 2 oil filters for a Veltrano Power VP-20, serial 120000");
  await customer.getByTestId("enquiry-submit").click();
  await customer.waitForURL(/\/workspace\/enquiries\/[0-9a-f-]{36}$/, { timeout: 20000 });
  const enquiryId = customer.url().split("/").pop();
  await customer.locator('[data-status="awaiting_review"]').first().waitFor({ timeout: 30000 });
  check("customer enquiry reaches human review", true);
  check("customer sees no review or admin navigation", (await customer.locator(".app-rail").innerText()).match(/review queue|users & access/i) === null);
  await customer.goto(`${BASE}/workspace/admin/users`);
  await customer.getByText(/don't have access/i).waitFor({ timeout: 15000 });
  check("customer direct navigation to admin is refused", true);
  // The API refuses on its own: call staff/admin endpoints with the customer's real bearer token.
  const auth = await new Promise((resolve) => {
    customer.on("request", (r) => { const h = r.headers().authorization; if (h && r.url().includes(":8000/")) resolve(h); });
    customer.reload();
  });
  const api = process.env.E2E_API_URL ?? "http://localhost:8000";
  const statuses = {};
  for (const path of ["/v1/staff/enquiries", `/v1/staff/enquiries/${enquiryId}`, "/v1/admin/members", "/v1/admin/audit", "/v1/admin/analytics"]) {
    statuses[path] = (await fetch(api + path, { headers: { authorization: auth } })).status;
  }
  check("customer token is refused by staff and admin APIs", Object.values(statuses).every((s) => s === 403 || s === 404), JSON.stringify(statuses));
  const forged = (await fetch(`${api}/v1/staff/enquiries`, { headers: { authorization: "Bearer not-a-real-token" } })).status;
  check("a forged bearer token is 401", forged === 401, String(forged));
  await customer.goto(`${BASE}/workspace/review/${enquiryId}`);
  await customer.getByText(/don't have access/i).waitFor({ timeout: 15000 });
  check("customer cannot open the review workspace", true);
  await customer.screenshot({ path: `${OUT}/a1-customer.png`, fullPage: true });

  // 3. Unassigned reviewer: the enquiry is invisible (scope, not just hidden links).
  await reviewer.goto(`${BASE}/workspace/review?status=`);
  await reviewer.locator("#main-workspace").waitFor();
  await reviewer.waitForTimeout(800);
  check("unassigned reviewer's queue does not list the enquiry", (await reviewer.locator(`[data-enquiry-id="${enquiryId}"]`).count()) === 0);
  await reviewer.goto(`${BASE}/workspace/review/${enquiryId}`);
  await reviewer.getByText(/not available/i).waitFor({ timeout: 15000 });
  check("unassigned reviewer gets 'not available' (404) for a real enquiry", true);

  // 4. Admin: sees everything, assigns to the reviewer, roles listed from Supabase.
  await admin.goto(`${BASE}/workspace/admin/users`);
  await admin.getByTestId("members-table").waitFor({ timeout: 20000 });
  const members = await admin.getByTestId("members-table").innerText();
  check("admin users screen lists Supabase accounts", ["customer@example.test", "reviewer@example.test", "admin@example.test"].every((e) => members.includes(e)));
  await admin.screenshot({ path: `${OUT}/a2-admin-users.png`, fullPage: true });
  await admin.goto(`${BASE}/workspace/review/${enquiryId}`);
  await admin.getByTestId("assign").waitFor({ timeout: 20000 });
  const reviewerOption = await admin.getByTestId("assign").locator("option", { hasText: /reviewer/i }).first().getAttribute("value");
  await admin.getByTestId("assign").selectOption(reviewerOption);
  await admin.getByText(/assigned to/i).waitFor({ timeout: 15000 });
  check("admin assigns the enquiry", true);

  // 5. Assigned reviewer: queue lists it, approves; session survives a reload.
  await reviewer.goto(`${BASE}/workspace/review?assigned=me`);
  await reviewer.locator(`[data-enquiry-id="${enquiryId}"]`).waitFor({ timeout: 20000 });
  check("assigned reviewer's queue lists the enquiry", true);
  await reviewer.reload();
  await reviewer.locator(`[data-enquiry-id="${enquiryId}"]`).waitFor({ timeout: 20000 });
  check("session restores after refresh", (await reviewer.locator("[data-entry]").getAttribute("data-entry")) === "account");
  await reviewer.goto(`${BASE}/workspace/review/${enquiryId}`);
  await reviewer.getByTestId("approve").click({ timeout: 20000 });
  await reviewer.getByRole("dialog").getByRole("button", { name: /approve & publish/i }).click();
  await reviewer.getByTestId("decision-outcome").waitFor({ timeout: 20000 });
  check("assigned reviewer approves", true);
  await reviewer.screenshot({ path: `${OUT}/a3-reviewer-approved.png`, fullPage: true });

  // 6. Customer sees the published reply.
  await customer.goto(`${BASE}/workspace/enquiries/${enquiryId}`);
  await customer.getByTestId("approved-reply").waitFor({ timeout: 20000 });
  check("customer sees the published recommendation", true);

  // 7. Audit trail shows the assignment and the decision.
  await admin.goto(`${BASE}/workspace/admin/audit`);
  await admin.getByTestId("audit-table").waitFor({ timeout: 20000 });
  const audit = await admin.getByTestId("audit-table").innerText();
  check("audit records assignment and approval", audit.includes("assignment.changed") && audit.includes("review.approved"));

  // 8. Sign-out: protected data no longer rendered; return-to after sign-in.
  await reviewer.getByTestId("sign-out").click();
  await reviewer.getByTestId("start-demo").waitFor({ timeout: 15000 });
  await reviewer.goto(`${BASE}/workspace/review/${enquiryId}`);
  await reviewer.getByTestId("start-demo").waitFor({ timeout: 15000 });
  check("after sign-out the review data is not shown", (await reviewer.getByTestId("review-workspace").count()) === 0);
  const again = await login(browser, "reviewer@example.test", "/workspace/review");
  check("sign-in returns to the requested page", again.page.url().includes("/workspace/review"), again.page.url());
  await again.ctx.close();
  const bad = await browser.newContext();
  const badPage = await bad.newPage();
  await badPage.goto(`${BASE}/login`);
  await badPage.getByTestId("login-email").fill("reviewer@example.test");
  await badPage.getByTestId("login-password").fill("wrong-password-123");
  await badPage.getByTestId("login-submit").click();
  await badPage.getByText(/sign-in failed/i).waitFor({ timeout: 15000 });
  check("a wrong password is refused", true);
  await bad.close();
  for (const s of Object.values(sessions)) await s.ctx.close();
} catch (err) {
  check("script completed", false, String(err).slice(0, 400));
} finally {
  await browser.close();
}
for (const r of results) console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}${r.detail ? `  (${r.detail})` : ""}`);
const failed = results.filter((r) => !r.ok).length;
console.log(failed ? `ACCOUNTS: ${failed} of ${results.length} check(s) failed` : `ACCOUNTS: all ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
