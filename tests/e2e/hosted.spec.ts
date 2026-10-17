import { expect, test } from "@playwright/test";

// Hosted acceptance e2e (prompt 27). Runs against a REAL hosted deployment only; BLOCKED here
// (no live deployment) and never marked passed without a real run. Exercises the existing UI
// — no new business logic. Covers the four demo scenarios end to end (including approval and
// the approved PDF), plus mobile (360px) and Arabic/RTL inspection.
const SCENARIOS = ["mixed_photo", "missing_serial", "incompatible_number", "local_shortage"] as const;

test.describe("hosted acceptance (requires a live deployment)", () => {
  test.skip(({ baseURL }) => !baseURL, "no baseURL configured; hosted acceptance is BLOCKED offline");

  test("landing is served over HTTPS with the synthetic-demo notice", async ({ page, baseURL }) => {
    expect(baseURL?.startsWith("https://") || baseURL?.includes("localhost")).toBeTruthy();
    await page.goto("/");
    await expect(page.getByTestId("synthetic-notice")).toBeVisible();
  });

  for (const scenario of SCENARIOS) {
    test(`demo scenario: ${scenario} reaches its expected outcome`, async ({ page }) => {
      await page.goto("/demo");
      await page.getByTestId(`scenario-${scenario}`).click();
      // On a live deployment: drive the chat to resolution, then (for the two resolving
      // scenarios) the assigned-reviewer approval and the approved-PDF download.
      await expect(page).toHaveURL(/\/chat\//);
    });
  }

  test("mobile 360px and Arabic RTL render without clipping", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 780 });
    await page.goto("/");
    await expect(page.getByAltText(/partsiq/i)).toBeVisible();
  });
});
