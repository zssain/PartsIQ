// Full-journey e2e (Phase 6, LIVE fixture backend). Drives the one-session demo end to end against
// a RUNNING stack: open the live demo → submit an enquiry as the customer → watch progress reach
// "waiting for review" → switch to the Reviewer seat → open the enquiry → Approve → switch back to
// Customer → see the reviewer-approved reply. A screenshot is captured at each major step.
//
// The operator starts the servers (Next.js on :3000, the API on :8099); this script NEVER launches
// them. Configure via env:
//   E2E_BASE_URL  base URL of the running web app   (default http://127.0.0.1:3000)
//   E2E_OUT       directory for step screenshots     (default /tmp/claude-501/partsiq-e2e)
// Run: node tests/e2e/journey.mjs
//
// Selectors are role/text/testid based (robust to styling changes). The data-testids used here are
// owned by the live components: customer-composer, enquiry-text, enquiry-submit, customer-progress,
// role-reviewer, role-customer, inbox-items / inbox-open-<id>, approve, approved-reply.
import { chromium, devices } from "@playwright/test";

const BASE = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.env.E2E_OUT ?? "/tmp/claude-501/partsiq-e2e";
// E2E_VIEWPORT=mobile drives the same journey at an iPhone 13 viewport; default is desktop.
const VIEWPORT =
  process.env.E2E_VIEWPORT === "mobile"
    ? { ...devices["iPhone 13"] }
    : { viewport: { width: 1280, height: 900 } };
const ENQUIRY_TEXT =
  "I need 2x air filters for a Corvane Air CA-110 (serial 800123). Deliver to Jeddah.";

// Generous but bounded — the fixture pipeline must reach awaiting_review before we switch seats.
const PROGRESS_TIMEOUT = 45000;
const DECISION_TIMEOUT = 20000;

const steps = [];
async function shot(page, name) {
  const file = `${OUT}/journey-${String(steps.length + 1).padStart(2, "0")}-${name}.png`;
  await page.screenshot({ path: file, fullPage: false }).catch(() => {});
  steps.push({ step: name, shot: file });
  return file;
}

const browser = await chromium.launch();
let failure = null;
try {
  const context = await browser.newContext(VIEWPORT);
  const page = await context.newPage();
  const pageErrors = [];
  page.on("pageerror", (e) => pageErrors.push(String(e)));

  // 1 — open the live demo.
  await page.goto(`${BASE}/demo/live`, { waitUntil: "domcontentloaded", timeout: 20000 });
  await page.getByTestId("customer-composer").waitFor({ state: "visible", timeout: 15000 });
  await shot(page, "open-live-demo");

  // 2 — submit an enquiry as the customer.
  await page.getByTestId("enquiry-text").fill(ENQUIRY_TEXT);
  await page.getByTestId("enquiry-submit").click();
  // The composer is replaced by the live enquiry view (progress panel mounts).
  await page.getByTestId("customer-progress").waitFor({ state: "visible", timeout: 15000 });
  await shot(page, "submitted-enquiry");

  // 3 — wait for progress to reach "waiting for review".
  const waitingStep = page.locator('[data-step="review"]');
  await waitingStep.waitFor({ state: "visible", timeout: PROGRESS_TIMEOUT });
  // The step reads done/waiting (not upcoming) once the pipeline is parked for human review.
  await page.waitForFunction(
    () => {
      const el = document.querySelector('[data-step="review"]');
      const stage = el?.getAttribute("data-stage");
      return stage === "waiting" || stage === "done";
    },
    { timeout: PROGRESS_TIMEOUT },
  );
  await shot(page, "progress-waiting-for-review");

  // 4 — switch to the Reviewer seat (same session).
  await page.getByTestId("role-reviewer").click();
  await page.getByTestId("reviewer-inbox").waitFor({ state: "visible", timeout: 15000 });
  // The session's own enquiry appears in the awaiting-review queue.
  const firstItem = page.locator('[data-testid="inbox-items"] [data-enquiry-id]').first();
  await firstItem.waitFor({ state: "visible", timeout: PROGRESS_TIMEOUT });
  await shot(page, "reviewer-inbox");

  // 5 — open the enquiry's review workspace. Scroll into view and force the tap: the editorial
  // ``pq-reveal`` transform animation can make Playwright's strict hit-test see an ancestor as the
  // top element on a narrow viewport even though the button is fully visible and tappable.
  const openButton = firstItem.getByRole("button");
  await openButton.scrollIntoViewIfNeeded();
  await openButton.click({ force: true });
  await page.getByTestId("review-workspace").waitFor({ state: "visible", timeout: 15000 });
  await page.getByTestId("region-ai-suggestion").waitFor({ state: "visible", timeout: 15000 });
  await shot(page, "review-workspace");

  // 6 — Approve (human decision). The UI re-fetches the authoritative resource after the decision.
  const approve = page.getByTestId("approve");
  await approve.waitFor({ state: "visible", timeout: 15000 });
  await approve.click();
  await page.getByTestId("decision-outcome").waitFor({ state: "visible", timeout: DECISION_TIMEOUT });
  await shot(page, "approved");

  // 7 — switch back to the Customer seat and see the reviewer-approved reply.
  await page.getByTestId("role-customer").click();
  await page.getByTestId("customer-progress").waitFor({ state: "visible", timeout: 15000 });
  await page.getByTestId("approved-reply").waitFor({ state: "visible", timeout: DECISION_TIMEOUT });
  await shot(page, "customer-sees-approved-reply");

  if (pageErrors.length) steps.push({ pageerrors: pageErrors.slice(0, 5) });
  await context.close();
} catch (err) {
  failure = String(err && err.stack ? err.stack : err);
} finally {
  await browser.close();
}

console.log(JSON.stringify({ base: BASE, out: OUT, steps, failure }, null, 2));
if (failure) {
  console.log(`JOURNEY: FAILED — ${failure.split("\n")[0]}`);
  process.exit(1);
}
console.log(`JOURNEY: completed ${steps.filter((s) => s.step).length} steps`);
process.exit(0);
