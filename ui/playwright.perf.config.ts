/**
 * The interface's performance check (`perf/`, AKS-121), started by
 * `tests/perf/test_interface.py` against a service it started; never part of `npm run e2e`.
 * `ITHAX_CHROMIUM` (or, for one release, its old name `LCSIM_CHROMIUM`; #70) names a
 * Chromium to use instead of Playwright's own download.
 */
import { defineConfig, devices } from "@playwright/test";

const executablePath = process.env.ITHAX_CHROMIUM || process.env.LCSIM_CHROMIUM;

export default defineConfig({
  testDir: "perf",
  testMatch: "*.perf.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 180_000,
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
