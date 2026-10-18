// Browser smoke check (Phase 6): render the redesigned PartsIQ UI at desktop + mobile against
// the live fixture backend, and verify the key pages mount without a runtime error overlay.
// Run: node tests/e2e/smoke.mjs  (requires Next.js on :3000 and the API on :8099)
import { chromium, devices } from "@playwright/test";

const BASE = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000";
const OUT = process.env.E2E_OUT ?? "/tmp/claude-501/partsiq-e2e";
const PAGES = ["/", "/demo", "/architecture", "/history", "/staff/inbox"];

const VIEWPORTS = [
  { name: "desktop", viewport: { width: 1280, height: 800 } },
  { name: "mobile", ...devices["iPhone 13"] },
];

function hasErrorOverlay(bodyText) {
  // Next.js dev error overlay / unhandled runtime error markers.
  return /Unhandled Runtime Error|Application error: a client-side exception/i.test(bodyText);
}

const results = [];
const browser = await chromium.launch();
try {
  for (const vp of VIEWPORTS) {
    const context = await browser.newContext({ viewport: vp.viewport, userAgent: vp.userAgent });
    const page = await context.newPage();
    const consoleErrors = [];
    page.on("pageerror", (e) => consoleErrors.push(String(e)));
    for (const path of PAGES) {
      const resp = await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded", timeout: 20000 });
      await page.waitForTimeout(400);
      const status = resp ? resp.status() : 0;
      const bodyText = await page.locator("body").innerText().catch(() => "");
      const heading = await page.locator("h1, h2, [role=heading]").first().innerText().catch(() => "");
      const ok = status < 500 && !hasErrorOverlay(bodyText) && bodyText.trim().length > 0;
      const file = `${OUT}/${vp.name}${path.replace(/\//g, "_") || "_root"}.png`;
      await page.screenshot({ path: file, fullPage: false }).catch(() => {});
      results.push({ vp: vp.name, path, status, ok, heading: heading.slice(0, 60), shot: file });
    }
    if (consoleErrors.length) results.push({ vp: vp.name, pageerrors: consoleErrors.slice(0, 3) });
    await context.close();
  }
} finally {
  await browser.close();
}

console.log(JSON.stringify(results, null, 2));
const failures = results.filter((r) => r.ok === false);
console.log(failures.length ? `BROWSER CHECK: ${failures.length} page(s) failed` : "BROWSER CHECK: all pages rendered");
process.exit(failures.length ? 1 : 0);
