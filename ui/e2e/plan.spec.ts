/**
 * The Canvas of an optimization model against a real service (AKS-137).
 *
 * A Plan project made on Home opens in the Table view; the product mix of spec 2, entered
 * by pointer (buttons, pickers and typing into fields; no keyboard shortcut), validates
 * with zero issues and saves `variables`, `objective` and `constraints` equal to
 * `benchmarks/product_mix/model.json`. The Diagram view shows the same model, and both
 * views meet WCAG 2.2 AA.
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";

const REPOSITORY = dirname(dirname(dirname(fileURLToPath(import.meta.url))));
const WCAG = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];
const benchmark = JSON.parse(
  readFileSync(join(REPOSITORY, "benchmarks", "product_mix", "model.json"), "utf8"),
) as Record<string, unknown>;

async function settled(page: Page): Promise<void> {
  await expect(page.locator(".save-state")).toHaveText("Saved");
  await expect(page.locator(".problems [role=status]")).not.toContainText("Checking");
}

/** Types into a field and leaves it by clicking the screen's title, which commits it. */
async function enter(page: Page, name: string, value: string): Promise<void> {
  const field = page.getByRole("textbox", { name, exact: true });
  await field.fill(value);
  await page.locator("#plan-heading").click();
  await settled(page);
  await expect(field).toHaveValue(value);
}

test("the product mix entered by pointer validates with no issues and equals the benchmark", async ({
  page,
  service,
  sent,
}) => {
  await service.api("PUT", "/v1/settings", { interface: { first_start_seen: true } });
  await page.goto(service.url);
  await page.getByRole("button", { name: "New empty project" }).click();
  const dialog = page.getByRole("dialog", { name: "New empty project" });
  await dialog.getByRole("textbox", { name: "Name" }).fill("Product mix");
  await dialog.getByRole("radio", { name: /Plan/ }).check();
  await dialog.getByRole("button", { name: "Create" }).click();
  await expect(page.getByRole("button", { name: "Table" })).toHaveAttribute("aria-pressed", "true");
  await settled(page);
  const pid = decodeURIComponent(new URL(page.url()).hash.split("/").pop() ?? "");

  for (const [index, name] of ["chairs", "tables"].entries()) {
    await page.getByRole("button", { name: "Add decision" }).click();
    await settled(page);
    await enter(page, `Name of decision ${index + 1}`, name);
    await enter(page, `Lower bound of ${name}`, "0");
  }
  await enter(page, "Coefficient of chairs in the goal", "45");
  await enter(page, "Coefficient of tables in the goal", "80");
  for (const [index, [name, chairs, tables, limit]] of [
    ["wood", "5", "20", "400"],
    ["labour", "10", "15", "450"],
  ].entries()) {
    await page.getByRole("button", { name: "Add limit" }).click();
    await settled(page);
    await enter(page, `Name of limit ${index + 1}`, name as string);
    await enter(page, `Coefficient of chairs in ${name}`, chairs as string);
    await enter(page, `Coefficient of tables in ${name}`, tables as string);
    await enter(page, `Limit of ${name}`, limit as string);
  }
  await expect(page.getByText("Maximize 45 × chairs + 80 × tables")).toBeVisible();
  await expect(page.locator(".problems [role=status]")).toHaveText("No problems");
  await expect(page.getByRole("button", { name: "Run", exact: true })).not.toHaveAttribute(
    "aria-disabled",
    "true",
  );

  const saved = (await service.api("GET", `/v1/projects/${pid}/model`)).body as {
    model: Record<string, unknown>;
  };
  for (const key of ["variables", "objective", "constraints"]) {
    expect(saved.model[key], key).toEqual(benchmark[key]);
  }
  const checked = await service.api("POST", `/v1/projects/${pid}/validate`);
  expect((checked.body as { issues: unknown[] }).issues).toEqual([]);
  // Every change went through the documented edits.
  expect(
    sent.some((request) => request.method === "POST" && request.path.endsWith("/model/edits")),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);

  // The Diagram view shows the same model; a card opens its row in the Table view.
  await page.getByRole("button", { name: "Diagram" }).click();
  await expect(page.getByRole("button", { name: "chairs decision, continuous ≥ 0" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Goal Maximize 45 × chairs + 80 × tables" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "wood 5 × chairs + 20 × tables ≤ 400" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "labour 10 × chairs + 15 × tables ≤ 450" }),
  ).toBeVisible();
  await expect(page.locator(".plan-line")).toHaveCount(6);
  expect((await new AxeBuilder({ page }).withTags(WCAG).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: /^labour/ }).click();
  await expect(page.getByRole("textbox", { name: "Name of limit 2" })).toBeFocused();
});
