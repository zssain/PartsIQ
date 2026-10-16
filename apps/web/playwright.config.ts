import { defineConfig, devices } from "@playwright/test";

// E2E config (prompt 18 scaffold; specs land in prompts 22/27). Chromium only; the dev
// server base URL is supplied by the environment so no production URL is hard-coded.
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:3000",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
