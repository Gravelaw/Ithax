/**
 * End-to-end tests against a real engine service (`e2e/service.ts`) and the built interface
 * (`npm run build` first). One worker: each test starts its own service on its own port.
 * `LCSIM_CHROMIUM` names a Chromium to use instead of Playwright's own download.
 */
import { defineConfig, devices } from "@playwright/test";

const executablePath = process.env.LCSIM_CHROMIUM;

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  reporter: [["list"]],
  use: {
    ...devices["Desktop Chrome"],
    viewport: { width: 1280, height: 800 },
    trace: "off",
    screenshot: "off",
    video: "off",
    ...(executablePath ? { launchOptions: { executablePath } } : {}),
  },
});
