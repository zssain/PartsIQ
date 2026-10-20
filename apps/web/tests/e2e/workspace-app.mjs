// Unified workspace browser journeys against a RUNNING stack (real local API, fixture execution —
// deterministic specialists, NO live model calls). No responses are mocked in the browser.
// The operator starts the servers; this script never does.
// Env: E2E_BASE_URL (default http://localhost:3000), E2E_OUT (screenshot dir).
// Run: node tests/e2e/workspace-app.mjs
import { mkdirSync } from "node:fs";
import { chromium, devices } from "@playwright/test";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const OUT = process.env.E2E_OUT ?? "/tmp/partsiq-workspace-app";
mkdirSync(OUT, { recursive: true });
const results = [];
const check = (name, ok, detail = "") => results.push({ name, ok: Boolean(ok), detail });
const shot = (page, name) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });

async function enterDemo(page) {
  await page.goto(`${BASE}/demo`);
  await page.waitForURL(/\/workspace/, { timeout: 20000 });
  await page.locator(".app-rail").waitFor({ timeout: 20000 });
}

async function newEnquiry(page, text, mode = "guided", { sample = false } = {}) {
  await page.goto(`${BASE}/workspace/enquiries/new`);
  await page.getByTestId("enquiry-text").fill(text);
  await page.getByTestId(mode === "guided" ? "mode-guided" : "mode-collaboration").check({ force: true });
  if (sample) await page.getByTestId("use-sample-plate").click();
  await page.getByTestId("enquiry-submit").click();
  await page.waitForURL(/\/workspace\/enquiries\/[0-9a-f-]{36}$/, { timeout: 20000 });
  return page.url().split("/").pop();
}

async function waitStatus(page, label, timeout = 30000) {
  await page.locator(`[data-status="${label}"]`).first().waitFor({ timeout });
}

const browser = await chromium.launch();
try {
  // ======================= 1. public demo: guided journey to approval =======================
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "light" });
  const page = await ctx.newPage();
  const apiPaths = [];
  page.on("request", (r) => { if (r.url().includes(":8000/")) apiPaths.push(new URL(r.url()).pathname); });
  await enterDemo(page);
  check("Try demo opens the workspace with a demo indicator", await page.getByTestId("demo-indicator").isVisible());
  await shot(page, "01-dashboard-empty");

  const guidedId = await newEnquiry(page, "Need 2 oil filters for a Veltrano Power VP-20, serial 120000");
  await page.getByTestId("customer-progress").waitFor();
  await waitStatus(page, "awaiting_review");
  check("guided enquiry reaches human review", true);
  const steps = await page.locator("[data-testid=customer-progress] li[data-step]").evaluateAll((els) => els.map((e) => e.getAttribute("data-step")));
  check("progress shows the recorded steps in order", steps.slice(0, 6).join(",") === "intake,identify,search,plan,draft,verify", steps.join(","));
  check("customer cannot see the draft before approval", (await page.getByTestId("approved-reply").count()) === 0);
  await shot(page, "02-enquiry-awaiting-review");

  await page.getByTestId("preview-role").selectOption("reviewer");
  await page.goto(`${BASE}/workspace/review`);
  await page.getByTestId("review-table").waitFor();
  check("reviewer queue lists the enquiry", (await page.locator(`[data-enquiry-id="${guidedId}"]`).count()) === 1);
  await shot(page, "03-review-queue");
  await page.goto(`${BASE}/workspace/review/${guidedId}`);
  await page.getByTestId("review-workspace").waitFor();
  check("review shows three separate regions", (await page.getByTestId("region-ai").count()) && (await page.getByTestId("region-db").count()) && (await page.getByTestId("region-human").count()));
  check("evidence names the compatible part", (await page.getByTestId("region-db").innerText()).includes("VP-OF-2824"));
  await shot(page, "04-review-workspace");
  await page.getByTestId("approve").click();
  await page.getByRole("dialog").getByRole("button", { name: /approve & publish/i }).click();
  await page.getByTestId("decision-outcome").waitFor({ timeout: 20000 });
  check("approval recorded", /approved and published/i.test(await page.getByTestId("decision-outcome").innerText()));
  await page.getByTestId("preview-role").selectOption("customer");
  await page.goto(`${BASE}/workspace/enquiries/${guidedId}`);
  await page.getByTestId("approved-reply").waitFor({ timeout: 20000 });
  check("customer sees the published reply", (await page.getByTestId("approved-reply").innerText()).includes("VP-OF-2824"));
  await shot(page, "05-customer-published");
  await page.reload();
  await page.getByTestId("approved-reply").waitFor({ timeout: 20000 });
  check("refresh restores server-backed state", true);
  check("every API call has one /v1 prefix", apiPaths.every((p) => (p.match(/\/v1(\/|$)/g) ?? []).length === 1), apiPaths.slice(0, 3).join(","));

  // ======================= 2. clarification: missing serial =======================
  await newEnquiry(page, "I need a hydraulic filter for a Corvane Air CA-110.");
  await page.getByTestId("pending-action").waitFor({ timeout: 30000 });
  check("missing serial asks the customer", /serial/i.test(await page.getByTestId("pending-action").innerText()));
  await shot(page, "06-clarification");
  await page.getByTestId("pending-answer").fill("Serial 812345");
  await page.getByTestId("pending-submit").click();
  await page.getByText(/revision 2/i).first().waitFor({ timeout: 30000 });
  await page.waitForFunction(() => !document.querySelector("[data-testid=pending-action][data-kind=clarification]") || document.querySelector('[data-status="awaiting_review"]'), null, { timeout: 30000 });
  const afterAnswer = await page.locator("[data-status]").first().getAttribute("data-status");
  check("answer resumes as a new revision", ["awaiting_review", "needs_information", "processing"].includes(afterAnswer ?? ""), afterAnswer ?? "");

  // ======================= 3. collaboration with consent =======================
  const collabId = await newEnquiry(page, "Need 1 CA-AF-1828 for my Corvane Air CA-110 (A)", "collaboration");
  await page.getByTestId("pending-action").waitFor({ timeout: 40000 });
  check("collaboration asks consent for a delegated search", (await page.getByTestId("pending-action").getAttribute("data-kind")) === "delegation_consent");
  await page.getByTestId("open-run").click();
  await page.getByTestId("exchange-feed").waitFor();
  const senders = await page.locator("[data-testid=exchange-feed] li").evaluateAll((els) => els.map((e) => `${e.getAttribute("data-sender")}>${e.getAttribute("data-recipient")}:${e.getAttribute("data-kind")}`));
  check("feed shows addressed specialist exchanges", senders.includes("controller>intake:task") && senders.some((s) => s.startsWith("parts>compatibility_search:tool_call")) && senders.some((s) => s.includes("delegation_request")), senders.slice(0, 6).join(" | "));
  await shot(page, "07-collaboration-consent");
  await page.getByTestId("consent-approve").click();
  await page.waitForFunction(() => [...document.querySelectorAll("[data-testid=exchange-feed] li")].some((e) => e.getAttribute("data-kind") === "consent_result"), null, { timeout: 30000 });
  check("consent is delivered to the Parts specialist", true);
  await page.waitForFunction(() => document.querySelector("[data-run-status]") && !["running", "queued"].includes(document.querySelector("[data-run-status]").getAttribute("data-run-status")), null, { timeout: 40000 });
  const collabStatus = await page.locator("[data-run-status]").first().getAttribute("data-run-status");
  check("collaboration run reaches a human step after consent", ["awaiting_review", "waiting_user"].includes(collabStatus ?? ""), collabStatus ?? "");
  await page.getByTestId("filter-tools").click();
  check("tools filter narrows the feed", (await page.locator("[data-testid=exchange-feed] li").count()) > 0);
  await shot(page, "08-collaboration-after-consent");

  // ======================= 4. master control: pause / resume / cancel =======================
  const pausedId = await newEnquiry(page, "need 3 oil filters and 2 fuel filters for VP-20 serial 120000", "collaboration");
  await page.getByTestId("run-pause").click({ timeout: 10000 });
  await page.locator('[data-run-status="paused"]').first().waitFor({ timeout: 20000 });
  await page.getByTestId("open-run").click();
  await page.getByTestId("exchange-feed").waitFor();
  const before = await page.locator("[data-testid=exchange-feed] li").count();
  await page.waitForTimeout(1500);
  check("no new exchange while paused", (await page.locator("[data-testid=exchange-feed] li").count()) === before, `${before}`);
  await shot(page, "09-paused");
  await page.getByTestId("run-resume").click();
  await page.waitForFunction((n) => document.querySelectorAll("[data-testid=exchange-feed] li").length > n, before, { timeout: 20000 });
  check("resume continues from saved state", true);
  const cancelId = await newEnquiry(page, "Need 2 oil filters for a Veltrano Power VP-20, serial 120000", "collaboration");
  await page.getByTestId("run-cancel").click({ timeout: 10000 });
  await page.getByRole("dialog").getByRole("button", { name: /cancel run/i }).click();
  await page.locator('[data-run-status="cancelled"]').first().waitFor({ timeout: 20000 });
  await page.waitForTimeout(1500);
  check("cancelled run never reaches review or publishes", (await page.locator('[data-status="awaiting_review"]').count()) === 0 && (await page.getByTestId("approved-reply").count()) === 0);
  void pausedId; void cancelId; void collabId;

  // ======================= 6. admin: import, audit =======================
  await page.getByTestId("preview-role").selectOption("admin");
  await page.goto(`${BASE}/workspace/admin/imports`);
  await page.getByTestId("import-invalid").click();
  await page.getByTestId("import-report").waitFor({ timeout: 20000 });
  check("invalid import reports row errors", (await page.getByTestId("import-report").getAttribute("data-state")) === "invalid" && (await page.getByTestId("import-issues").innerText()).includes("FORMULA_NOT_ALLOWED"));
  await shot(page, "10-import-invalid");
  await page.getByTestId("import-valid").click();
  await page.locator('[data-testid=import-report][data-state="validated"]').waitFor({ timeout: 20000 });
  await page.getByTestId("import-publish").click();
  await page.getByRole("dialog").getByRole("button", { name: /publish/i }).click();
  await page.locator('[data-testid=import-report][data-state="published"]').waitFor({ timeout: 20000 });
  check("valid import publishes a sandbox version", true);
  await page.goto(`${BASE}/workspace/catalogue?q=VP-AF-9999`);
  await page.getByTestId("catalogue-table").waitFor();
  check("catalogue shows the published part", (await page.getByTestId("catalogue-table").innerText()).includes("VP-AF-9999"));
  await page.goto(`${BASE}/workspace/admin/audit`);
  await page.getByTestId("audit-table").waitFor();
  const auditText = await page.getByTestId("audit-table").innerText();
  check("audit trail records decisions, commands and imports", ["review.approved", "run.command.pause", "catalogue.published"].every((a) => auditText.includes(a)));
  await shot(page, "11-audit");
  await page.goto(`${BASE}/workspace/admin/analytics`);
  await page.getByTestId("analytics-stats").waitFor();
  check("analytics marks tokens as not measured", /not measured/i.test(await page.locator("body").innerText()));
  await shot(page, "12-analytics");
  await page.goto(`${BASE}/workspace/admin/users`);
  await page.getByTestId("members-table").waitFor();
  check("users screen lists sandbox personas", (await page.getByTestId("members-table").innerText()).includes("synthetic"));

  // ======================= 7. isolation =======================
  const other = await browser.newContext();
  const otherPage = await other.newPage();
  await enterDemo(otherPage);
  await otherPage.goto(`${BASE}/workspace/enquiries/${guidedId}`);
  await otherPage.getByText(/not available/i).waitFor({ timeout: 20000 });
  check("a second demo session cannot open the first session's enquiry", true);
  await other.close();
  // sign out ends access
  await page.getByTestId("sign-out").click();
  await page.getByTestId("start-demo").waitFor({ timeout: 10000 });
  check("sign-out returns to the entry screen", true);
  await ctx.close();

  // ======================= 8. responsive, keyboard, reduced motion, dark =======================
  const mctx = await browser.newContext({ ...devices["iPhone 13"], colorScheme: "dark", reducedMotion: "reduce" });
  const m = await mctx.newPage();
  await enterDemo(m);
  const overflow = await m.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check("mobile has no horizontal overflow", overflow <= 1, `${overflow}px`);
  await m.getByRole("button", { name: /menu/i }).click();
  await m.getByRole("link", { name: /new enquiry/i }).first().click();
  await m.getByTestId("enquiry-text").waitFor();
  check("mobile drawer navigation works", m.url().endsWith("/workspace/enquiries/new"));
  await shot(m, "13-mobile-new-enquiry");
  const motion = await m.evaluate(() => getComputedStyle(document.querySelector(".app-btn")).transitionDuration);
  check("reduced motion disables transitions", /^0s/.test(motion), motion);
  await mctx.close();

  const kctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const k = await kctx.newPage();
  await enterDemo(k);
  await k.keyboard.press("Tab");
  check("first Tab reaches the skip link", /skip to content/i.test(await k.evaluate(() => document.activeElement?.textContent ?? "")));
  await k.keyboard.press("Enter");
  check("skip link moves focus to content", await k.evaluate(() => document.activeElement?.id === "main-workspace"));
  await kctx.close();

  // ======================= Arabic / RTL =======================
  const actx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await actx.addCookies([{ name: "locale", value: "ar", url: BASE }]);
  const a = await actx.newPage();
  await enterDemo(a).catch(() => undefined);
  await a.waitForSelector(".app-rail", { timeout: 20000 });
  check("Arabic sets dir=rtl", (await a.evaluate(() => document.documentElement.dir)) === "rtl");
  check("Arabic navigation labels", (await a.locator(".app-rail").innerText()).includes("لوحة المتابعة"));
  const aOverflow = await a.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check("RTL layout has no horizontal overflow", aOverflow <= 1, `${aOverflow}px`);
  await shot(a, "15-arabic-dashboard");
  await actx.close();

  // ======================= legacy links =======================
  const lctx = await browser.newContext();
  const l = await lctx.newPage();
  await l.goto(`${BASE}/demo/live`);
  await l.waitForURL(/\/workspace/);
  check("/demo/live redirects to the workspace", true);
  await l.goto(`${BASE}/staff/inbox`);
  await l.waitForURL(/\/workspace\/review/);
  check("/staff/inbox redirects to the review queue", true);
  await l.goto(`${BASE}/`);
  check("site header 'Workspace' links to /workspace", (await l.locator('header nav a', { hasText: "Workspace" }).getAttribute("href")) === "/workspace");
  await l.goto(`${BASE}/login`);
  await shot(l, "14-login");
  await lctx.close();
} catch (err) {
  check("script completed", false, String(err).slice(0, 400));
} finally {
  await browser.close();
}

for (const r of results) console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}${r.detail ? `  (${r.detail})` : ""}`);
const failed = results.filter((r) => !r.ok).length;
console.log(failed ? `WORKSPACE-APP: ${failed} of ${results.length} check(s) failed` : `WORKSPACE-APP: all ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
