// Command-workspace browser checks (/demo/live) against a RUNNING fixture stack. Complements
// journey.mjs (which covers submit → review → approve) with the shell behaviours added by the
// command-workspace update:
//   1. workspace navigation + browser Back/Forward
//   2. refresh restores the active enquiry (same tab)
//   3. "New enquiry" starts fresh while the earlier server record stays readable
//   4. reviewer rejection re-fetches authoritative state; customer sees no published reply
//   5. keyboard: skip link and workspace nav reachable/operable with the keyboard
//   6. reduced motion: no transitions/animations inside the console
//   7. every API request carries exactly one /v1 segment
//   8. light/dark theme toggle + screenshots at desktop and mobile
// The operator starts the servers; this script never does. Env: E2E_BASE_URL, E2E_OUT.
// Run: node tests/e2e/workspace.mjs
import { chromium, devices } from "@playwright/test";

const BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const OUT = process.env.E2E_OUT ?? "/tmp/partsiq-workspace";
const API = process.env.E2E_API_URL ?? "http://localhost:8000";
const results = [];
const check = (name, ok, detail = "") => results.push({ name, ok: Boolean(ok), detail });

async function submitEnquiry(page, text) {
  await page.getByTestId("enquiry-text").fill(text);
  await page.getByTestId("enquiry-submit").click();
  await page.getByTestId("customer-progress").waitFor({ timeout: 20000 });
}

const browser = await chromium.launch();
try {
  // ---------------- desktop, light, full behaviour checks ----------------
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 }, colorScheme: "light" });
  const page = await ctx.newPage();
  const apiUrls = [];
  page.on("request", (r) => { if (r.url().includes("/v1")) apiUrls.push(r.url()); });

  await page.goto(`${BASE}/demo/live`);
  await page.getByTestId("customer-composer").waitFor({ timeout: 20000 });
  await page.screenshot({ path: `${OUT}/desktop-light-enquiry.png` });

  // 2. create + refresh restores
  await submitEnquiry(page, "Need 2 air filters for a Corvane Air CA-110, serial 800123. Deliver to Jeddah.");
  const firstId = await page.evaluate(() => sessionStorage.getItem("pq-active-enquiry"));
  check("enquiry id stored for this tab", firstId);
  await page.reload();
  await page.getByTestId("customer-progress").waitFor({ timeout: 20000 });
  check("refresh restores the active enquiry", (await page.evaluate(() => sessionStorage.getItem("pq-active-enquiry"))) === firstId
    && (await page.getByTestId("customer-composer").count()) === 0);

  // 1. navigation + Back/Forward
  await page.getByRole("button", { name: /specialist activity/i }).click();
  check("nav updates the URL", page.url().endsWith("?view=activity"));
  await page.getByRole("button", { name: /^overview$/i }).click();
  await page.getByText(/agent collaboration/i).waitFor();
  await page.screenshot({ path: `${OUT}/desktop-light-overview.png` });
  await page.goBack();
  check("Back returns to the previous screen", page.url().endsWith("?view=activity"));
  await page.screenshot({ path: `${OUT}/desktop-light-activity.png` });
  await page.goForward();
  check("Forward re-opens the next screen", page.url().endsWith("?view=overview")
    && (await page.getByText(/not connected/i).count()) > 0);
  check("collaboration stays labelled 'Not connected', no pause/resume/cancel controls",
    (await page.getByRole("button", { name: /pause|resume|cancel/i }).count()) === 0);
  await page.getByRole("button", { name: /access & controls/i }).click();
  await page.screenshot({ path: `${OUT}/desktop-light-access.png` });

  // 3. new enquiry is non-destructive
  await page.getByRole("button", { name: /new enquiry/i }).click();
  await page.getByTestId("customer-composer").waitFor();
  check("New enquiry clears the active pointer", (await page.evaluate(() => sessionStorage.getItem("pq-active-enquiry"))) === null);
  const stillThere = await page.evaluate(async ([id, api]) => {
    const tk = sessionStorage.getItem("pq-demo-token") ?? "";
    const r = await fetch(`${api}/v1/enquiries/${id}`, { headers: { "X-Demo-Token": tk } });
    return r.status;
  }, [firstId, API]);
  check("earlier enquiry still exists on the server after New enquiry", stillThere === 200, `status=${stillThere}`);

  // 4. rejection path re-fetches authoritative state
  await submitEnquiry(page, "Need an oil filter for a CAT 320.");
  await page.waitForFunction(() => document.querySelector('[data-step="review"]')?.getAttribute("data-stage") !== "upcoming", null, { timeout: 30000 });
  await page.getByTestId("role-reviewer").click();
  const item = page.locator('[data-testid="inbox-items"] [data-enquiry-id]').first();
  await item.waitFor({ timeout: 20000 });
  await item.getByRole("button").click({ force: true });
  await page.getByTestId("review-workspace").waitFor({ timeout: 20000 });
  await page.screenshot({ path: `${OUT}/desktop-light-review.png` });
  await page.getByTestId("reject-reason").fill("Please send a nameplate photo.");
  await page.getByTestId("reject").click();
  await page.getByTestId("decision-outcome").waitFor({ timeout: 20000 });
  const outcome = await page.getByTestId("decision-outcome").innerText();
  check("rejection shows the server-confirmed status", /rejected/i.test(outcome), outcome);
  await page.getByTestId("role-customer").click();
  await page.getByTestId("customer-progress").waitFor({ timeout: 20000 });
  check("rejected enquiry publishes no reply", (await page.getByTestId("approved-reply").count()) === 0);

  // 8. theme toggle
  const toggle = page.getByRole("button", { name: /switch to (dark|light) theme/i });
  await toggle.click();
  const themeAfter = await page.evaluate(() => document.documentElement.getAttribute("data-theme"));
  check("theme toggle switches data-theme", themeAfter === "dark", `data-theme=${themeAfter}`);
  await page.screenshot({ path: `${OUT}/desktop-dark-enquiry.png` });

  // 7. one /v1 per request
  const bad = apiUrls.filter((u) => (new URL(u).pathname.match(/\/v1(\/|$)/g) ?? []).length !== 1);
  check("every API request has exactly one /v1", apiUrls.length > 0 && bad.length === 0, `${apiUrls.length} requests, bad=${bad.slice(0, 2).join(",")}`);
  await ctx.close();

  // ---------------- keyboard + reduced motion ----------------
  const kctx = await browser.newContext({ viewport: { width: 1366, height: 900 }, reducedMotion: "reduce" });
  const kpage = await kctx.newPage();
  await kpage.goto(`${BASE}/demo/live`);
  await kpage.getByTestId("customer-composer").waitFor({ timeout: 20000 });
  await kpage.keyboard.press("Tab");
  const firstFocus = await kpage.evaluate(() => document.activeElement?.textContent ?? "");
  check("first Tab reaches the skip link", /skip to workspace content/i.test(firstFocus), firstFocus);
  await kpage.getByRole("button", { name: /^overview$/i }).focus();
  await kpage.keyboard.press("Enter");
  check("workspace nav operates with Enter", kpage.url().endsWith("?view=overview"));
  const motion = await kpage.evaluate(() => {
    const el = document.querySelector(".pq-console nav button");
    const cs = el ? getComputedStyle(el) : null;
    return cs ? `${cs.transitionDuration}|${cs.animationName}` : "missing";
  });
  check("reduced motion disables console transitions", /^0s/.test(motion) && motion.endsWith("|none"), motion);
  await kctx.close();

  // ---------------- mobile, dark ----------------
  const mctx = await browser.newContext({ ...devices["iPhone 13"], colorScheme: "dark" });
  const mpage = await mctx.newPage();
  await mpage.goto(`${BASE}/demo/live`);
  await mpage.getByTestId("customer-composer").waitFor({ timeout: 20000 });
  const overflow = await mpage.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  check("mobile has no horizontal page overflow", overflow <= 1, `overflow=${overflow}px`);
  // Page-level overflow misses content clipped INSIDE a bar; check the console chrome directly.
  const clipped = await mpage.evaluate(() => [".pq-console-top", ".pq-console-heading", ".pq-console-toolbar"]
    .map((s) => document.querySelector(s)).filter(Boolean)
    .filter((el) => el.scrollWidth - el.clientWidth > 1).map((el) => el.className));
  check("mobile console chrome has no clipped content", clipped.length === 0, clipped.join(","));
  const shell = await mpage.evaluate(() => { const r = document.querySelector(".pq-console").getBoundingClientRect(); return `${Math.round(r.left)},${Math.round(r.width)}/${window.innerWidth}`; });
  check("console is full-bleed (not boxed by the page wrapper)", shell.startsWith("0,"), shell);
  check("mobile shows the synthetic-data label", (await mpage.getByText("Synthetic demo").count()) > 0);
  check("mobile keeps the EN/AR control", (await mpage.getByRole("group", { name: /language/i }).count()) > 0);
  await mpage.screenshot({ path: `${OUT}/mobile-dark-enquiry.png`, fullPage: true });
  await mpage.getByRole("button", { name: /^overview$/i }).click();
  await mpage.screenshot({ path: `${OUT}/mobile-dark-overview.png`, fullPage: true });
  await mctx.close();
} catch (err) {
  check("script completed", false, String(err).slice(0, 300));
} finally {
  await browser.close();
}

for (const r of results) console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}${r.detail ? `  (${r.detail})` : ""}`);
const failed = results.filter((r) => !r.ok).length;
console.log(failed ? `WORKSPACE: ${failed} check(s) failed` : `WORKSPACE: all ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
