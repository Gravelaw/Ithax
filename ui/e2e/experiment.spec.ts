/**
 * The Experiment screen against a real service (AKS-120; the AKS-121 gate).
 *
 * A Process project made on Home has the `base` experiment of a new project (8 h, 0 s, 30
 * repeat runs). Set by pointer on the Experiment screen (pickers, and typing into fields
 * that are committed by clicking elsewhere), the coffee shop's `base` experiment (200 h,
 * 10 h warm-up, 30 replications, seed 12345) is saved equal to `examples/coffee_shop.json`'s
 * `experiments`, through `set_experiment` edits only. A scenario is added and removed, and
 * the screen meets WCAG 2.2 AA.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";

const REPOSITORY = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const coffeeShop = JSON.parse(
  readFileSync(join(REPOSITORY, "examples", "coffee_shop.json"), "utf8"),
) as { experiments: unknown[] };

async function settled(page: Page): Promise<void> {
  await expect(page.locator(".save-state")).toHaveText("Saved");
}

/** Types into a field and leaves it by clicking the experiment's title, which commits it. */
async function enter(page: Page, name: string, value: string): Promise<void> {
  const field = page.getByRole("textbox", { name, exact: true });
  await field.fill(value);
  await page.locator("#experiment-id-heading").click();
  await settled(page);
  await expect(field).toHaveValue(value);
}

test("the coffee shop's base experiment set by pointer equals the example's", async ({
  page,
  service,
  sent,
}) => {
  await service.api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
  await page.goto(service.url);
  await page.getByRole("button", { name: "New empty project" }).click();
  const dialog = page.getByRole("dialog", { name: "New empty project" });
  await dialog.getByRole("textbox", { name: "Name" }).fill("Coffee shop");
  await dialog.getByRole("button", { name: "Create" }).click();
  await settled(page);
  const pid = decodeURIComponent(new URL(page.url()).hash.split("/").pop() ?? "");

  await page
    .getByRole("navigation", { name: "Screens" })
    .getByRole("button", { name: "Experiment" })
    .click();
  await expect(page.getByRole("heading", { name: "base", exact: true })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Run length" })).toHaveValue("8");
  await expect(page.getByRole("combobox", { name: "Unit of Run length" })).toHaveValue("h");

  const before = sent.length;
  await enter(page, "Run length", "200");
  await page.getByRole("combobox", { name: "Unit of Settling-in time" }).selectOption("h");
  await settled(page);
  await enter(page, "Settling-in time", "10");
  await expect(page.getByRole("textbox", { name: "Repeat runs" })).toHaveValue("30");
  await enter(page, "Seed", "12345");

  const saved = (await service.api("GET", `/v1/projects/${pid}/model`)).body as {
    model: { experiments: unknown[] };
  };
  expect(saved.model.experiments).toEqual(coffeeShop.experiments);
  const checked = await service.api("POST", `/v1/projects/${pid}/validate`);
  expect((checked.body as { issues: unknown[] }).issues).toEqual([]);
  // Every change was a documented model edit, and only documented routes were used.
  const writes = sent.slice(before).filter((request) => request.method !== "GET");
  expect(writes.length).toBeGreaterThan(0);
  for (const request of writes) {
    expect([`/v1/projects/${pid}/model/edits`, `/v1/projects/${pid}/validate`]).toContain(
      request.path,
    );
  }
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);

  // A scenario: added, shown, then removed; undo puts it back.
  const added = page.getByRole("textbox", { name: "New scenario id" });
  await added.fill("busy_day");
  await page.getByRole("button", { name: "Add scenario" }).click();
  await settled(page);
  await expect(page.getByRole("rowheader", { name: "busy_day" })).toBeVisible();
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: "Remove scenario busy_day" }).click();
  await settled(page);
  await expect(page.getByRole("rowheader", { name: "busy_day" })).toHaveCount(0);
  await page.getByRole("button", { name: "Undo: remove scenario busy_day" }).click();
  await settled(page);
  await expect(page.getByRole("rowheader", { name: "busy_day" })).toBeVisible();
});
