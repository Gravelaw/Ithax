/**
 * The Settings screen against a real service (AKS-138): it reads and writes each key of
 * `/v1/settings`, says when each takes effect, shows the service's W220 issue for a
 * threshold in `settings.json` it cannot use and its E184 issues for a refused value, and
 * restores the preferences after a question. It meets WCAG 2.2 AA.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";

const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

/** Types into a field and presses Enter, then waits for the saved value. */
async function enter(page: Page, name: string, value: string): Promise<void> {
  const field = page.getByRole("textbox", { name, exact: true });
  await field.fill(value);
  await field.press("Enter");
  await expect(page.getByRole("textbox", { name, exact: true })).toHaveValue(value);
}

test("Settings reads and writes every key and shows the service's issues", async ({
  page,
  service,
}) => {
  await service.api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
  // A threshold the service cannot use, written in the file by hand.
  const file = join(service.configDir, "settings.json");
  const stored = JSON.parse(readFileSync(file, "utf8")) as Record<string, unknown>;
  writeFileSync(
    file,
    JSON.stringify({ ...stored, finding_thresholds: { bottleneck_utilization: 2 } }),
  );
  await page.goto(service.url);
  await page
    .getByRole("navigation", { name: "Screens" })
    .getByRole("button", { name: "Settings" })
    .click();
  await expect(page.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
  await expect(page.locator(".settings-screen .problem")).toContainText("W220");
  await expect(page.getByText(/^Detected: \d+ cores/)).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "simpy" })).toBeVisible();
  await expect(page.getByRole("rowheader", { name: "highs" })).toBeVisible();
  await expect(
    page.getByText(/Takes effect at the next start of the engine service/).first(),
  ).toBeVisible();
  await expect(page.getByText(/^Takes effect at the next results you open/)).toBeVisible();
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);

  await enter(page, "Runs at once", "2");
  await enter(page, "Time limit, in seconds", "1200");
  await enter(page, "Memory limit, in bytes", "4000000000");
  await page.getByRole("combobox", { name: "Tier at the next start" }).selectOption("high");
  await enter(page, "Bottleneck at", "0.9");
  await expect(page.locator(".settings-screen .problem")).toHaveCount(0);
  await enter(page, "Idle below", "0.2");
  await enter(page, "Likely range wider than", "0.05");
  await enter(page, "Shortest time judged, in seconds", "30");
  await enter(page, "Lowest rate judged, per second", "0.001");
  // Emptying a threshold restores its default (review of PR #48).
  await page.getByRole("textbox", { name: "Idle below", exact: true }).fill("");
  await page.getByRole("textbox", { name: "Idle below", exact: true }).press("Enter");
  await expect(page.getByRole("textbox", { name: "Idle below", exact: true })).toHaveValue("0.3");
  await enter(page, "Idle below", "0.2");
  await page.getByRole("radio", { name: "Dark" }).check();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("radio", { name: "125%" }).check();
  await page.getByRole("radio", { name: "Off" }).check();
  await page.getByRole("checkbox", { name: "Colour-blind safe charts" }).check();
  await page.getByRole("checkbox", { name: "Ask before deleting" }).uncheck();
  await enter(page, "Undo steps", "300");
  await expect(page.locator("html")).toHaveAttribute("data-charts", "colour-blind");
  const written = (await service.api("GET", "/v1/settings")).body as {
    settings: Record<string, unknown>;
  };
  expect(written.settings).toEqual({
    tier: "high",
    max_concurrent_runs: 2,
    run_time_limit_s: 1200,
    run_memory_limit_bytes: 4000000000,
    finding_thresholds: {
      bottleneck_utilization: 0.9,
      idle_utilization: 0.2,
      relative_half_width: 0.05,
      min_time_s: 30,
      min_rate_per_s: 0.001,
    },
    interface: {
      first_start_seen: true,
      ask_before_deleting: false,
      undo_steps: 300,
      theme: "dark",
      text_size: 125,
      motion: "off",
      colour_blind_charts: true,
    },
  });
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);

  // A value the service refuses: its E184 issue, and the saved value shown again.
  await page.getByRole("textbox", { name: "Runs at once", exact: true }).fill("lots");
  await page.getByRole("textbox", { name: "Runs at once", exact: true }).press("Enter");
  await expect(page.getByRole("alert")).toContainText("E184");
  await expect(page.getByRole("textbox", { name: "Runs at once", exact: true })).toHaveValue("2");

  // Restore all defaults: the preferences only, after a question.
  await page.getByRole("button", { name: "Restore all defaults" }).click();
  const dialog = page.getByRole("dialog", { name: "Restore all defaults?" });
  await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();
  await dialog.getByRole("button", { name: "Restore" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "system");
  const restored = (await service.api("GET", "/v1/settings")).body as {
    settings: { tier: string; interface: Record<string, unknown> };
  };
  expect(restored.settings.tier).toBe("high");
  expect(restored.settings.interface).toEqual({
    first_start_seen: true,
    ask_before_deleting: true,
    undo_steps: null,
    theme: "system",
    text_size: 100,
    motion: "system",
    colour_blind_charts: false,
  });
});
