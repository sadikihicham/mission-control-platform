import { defineConfig, devices } from "@playwright/test";

// QA E2E Agent Control (P9, gap 3) — multi-tenant, multi-profil, a11y.
//
// La stack (API + web) est démarrée hors config (voir scripts/e2e-run.sh) sur des
// ports décalés pour ne pas entrer en collision avec la stack docker partagée.
// `E2E_BASE_URL` / `E2E_API_URL` pointent l'instance isolée.
const BASE_URL = process.env.E2E_BASE_URL ?? "http://localhost:3200";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: BASE_URL,
    headless: true,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
